import base64
import json
import requests
from config import JUPITER_QUOTE_API, JUPITER_SWAP_API, WSOL_MINT, SLIPPAGE_BPS, RPC_URL

HEADERS = {"User-Agent": "Mozilla/5.0"}


FALLBACK_RPCS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-rpc.publicnode.com",
]


def get_wallet_sol_balance(wallet_address: str, rpc_url: str = RPC_URL) -> float:
    """
    Fetches the real-time SOL balance of a wallet from the RPC node.
    """
    targets = [rpc_url] + [r for r in FALLBACK_RPCS if r != rpc_url]
    payload = {"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [wallet_address]}
    for endpoint in targets:
        try:
            res = requests.post(endpoint, json=payload, headers={"Content-Type": "application/json"}, timeout=5).json()
            lamports = res.get("result", {}).get("value", 0)
            return lamports / 1_000_000_000
        except Exception:
            continue
    return 0.0


def send_raw_transaction_rpc(raw_tx_bytes: bytes, rpc_url: str = RPC_URL) -> str:
    """
    Submits a signed raw transaction directly to Solana JSON-RPC with automatic failover.
    Returns the transaction signature (tx_id).
    """
    targets = [rpc_url] + [r for r in FALLBACK_RPCS if r != rpc_url]
    tx_base64 = base64.b64encode(raw_tx_bytes).decode("utf-8")
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "sendTransaction",
        "params": [
            tx_base64,
            {
                "encoding": "base64",
                "skipPreflight": True,
                "preflightCommitment": "processed",
                "maxRetries": 3,
            },
        ],
    }

    last_err = None
    for endpoint in targets:
        try:
            res = requests.post(endpoint, json=payload, headers={"Content-Type": "application/json"}, timeout=8)
            data = res.json()
            if "error" in data:
                raise RuntimeError(f"RPC Error ({endpoint}): {data['error']}")
            return data["result"]
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(f"All RPC endpoints failed. Last error: {last_err}")


def get_quote(input_mint: str, output_mint: str, amount_raw: int, slippage_bps: int = SLIPPAGE_BPS):
    """
    Fetches real-time routing quote from Jupiter v1 API.
    """
    params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": amount_raw,
        "slippageBps": slippage_bps,
    }
    try:
        response = requests.get(JUPITER_QUOTE_API, params=params, headers=HEADERS, timeout=8)
        data = response.json()
        if "routePlan" not in data:
            return None
        return data
    except Exception:
        return None


def get_sell_value_sol(token_mint: str, token_amount_raw: int, slippage_bps: int = 500) -> float:
    """
    Simulates selling the entire token balance for WSOL.
    Returns the exact net SOL receivable (accounting for price impact and pool fees).
    """
    quote = get_quote(token_mint, WSOL_MINT, token_amount_raw, slippage_bps)
    if not quote or "outAmount" not in quote:
        return 0.0
    return int(quote["outAmount"]) / 1_000_000_000


def execute_swap(
    input_mint: str,
    output_mint: str,
    amount_raw: int,
    keypair,
    slippage_bps: int = SLIPPAGE_BPS,
    rpc_url: str = RPC_URL
) -> tuple[str | None, int]:
    """
    Compiles, signs, and broadcasts a swap transaction via Jupiter.
    Returns (transaction_id, out_amount_received).
    """
    wallet_address = str(keypair.pubkey())

    quote = get_quote(input_mint, output_mint, amount_raw, slippage_bps)
    if not quote:
        print("❌ Route unavailable on Jupiter.")
        return None, 0

    expected_out = int(quote.get("outAmount", 0))

    payload = {
        "quoteResponse": quote,
        "userPublicKey": wallet_address,
        "wrapAndUnwrapSol": True,
        "dynamicComputeUnitLimit": True,
        "prioritizationFeeLamports": "auto"
    }

    try:
        swap_res = requests.post(JUPITER_SWAP_API, json=payload, headers=HEADERS, timeout=10).json()
        if "swapTransaction" not in swap_res:
            print(f"❌ Swap build failed: {swap_res.get('error', swap_res)}")
            return None, 0

        from solders.transaction import VersionedTransaction

        raw_tx_bytes = base64.b64decode(swap_res["swapTransaction"])
        versioned_tx = VersionedTransaction.from_bytes(raw_tx_bytes)

        # Sign message locally
        signature = keypair.sign_message(bytes(versioned_tx.message))
        signed_tx = VersionedTransaction.populate(versioned_tx.message, [signature])

        # Broadcast via direct JSON-RPC
        tx_id = send_raw_transaction_rpc(bytes(signed_tx), rpc_url)
        return tx_id, expected_out

    except Exception as error:
        print(f"🚨 Execution error: {error}")
        return None, 0


def buy_token(token_mint: str, sol_amount: float, keypair, slippage_bps: int = SLIPPAGE_BPS, rpc_url: str = RPC_URL):
    """Buys target token with SOL."""
    lamports = int(sol_amount * 1_000_000_000)
    return execute_swap(WSOL_MINT, token_mint, lamports, keypair, slippage_bps, rpc_url)


def sell_token(token_mint: str, token_amount_raw: int, keypair, slippage_bps: int = SLIPPAGE_BPS, rpc_url: str = RPC_URL):
    """Sells target token back to SOL."""
    return execute_swap(token_mint, WSOL_MINT, token_amount_raw, keypair, slippage_bps, rpc_url)
