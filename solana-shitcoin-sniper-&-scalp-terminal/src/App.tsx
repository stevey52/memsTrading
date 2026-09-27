import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Terminal,
  Activity,
  ShieldAlert,
  ShieldCheck,
  TrendingUp,
  TrendingDown,
  Play,
  Pause,
  Zap,
  AlertTriangle,
  Search,
  Trash2,
  Sliders,
  Volume2,
  VolumeX,
  FileCode,
  Download,
  Radio,
  ArrowUpRight,
  Lock,
  Timer,
  Wallet,
  Globe,
  Send,
  Twitter,
  Copy,
  Check,
  ExternalLink,
  X,
  Sparkles,
  Layers,
  ArrowDownRight,
  Gauge,
  Percent,
  Cpu,
  History,
  Clock,
  ArrowUpDown,
  CheckCircle2,
  Filter,
  Coins,
  BarChart3
} from 'lucide-react';

// --- Sound Synthesizer via Native Web Audio API ---
class SoundManager {
  private ctx: AudioContext | null = null;
  public enabled: boolean = true;

  private init() {
    if (!this.ctx && typeof window !== 'undefined') {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (AudioCtx) {
        this.ctx = new AudioCtx();
      }
    }
  }

  playBuy() {
    if (!this.enabled) return;
    try {
      this.init();
      if (!this.ctx) return;
      const now = this.ctx.currentTime;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(440, now);
      osc.frequency.exponentialRampToValueAtTime(880, now + 0.12);
      gain.gain.setValueAtTime(0.12, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.18);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(now);
      osc.stop(now + 0.18);
    } catch {
      // AudioContext policy fallback
    }
  }

  playTakeProfit() {
    if (!this.enabled) return;
    try {
      this.init();
      if (!this.ctx) return;
      const notes = [523.25, 659.25, 783.99, 1046.5]; // C5, E5, G5, C6
      notes.forEach((freq, idx) => {
        const now = this.ctx!.currentTime + idx * 0.08;
        const osc = this.ctx!.createOscillator();
        const gain = this.ctx!.createGain();
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(freq, now);
        gain.gain.setValueAtTime(0.15, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.22);
        osc.connect(gain);
        gain.connect(this.ctx!.destination);
        osc.start(now);
        osc.stop(now + 0.22);
      });
    } catch {}
  }

  playStopLoss() {
    if (!this.enabled) return;
    try {
      this.init();
      if (!this.ctx) return;
      const now = this.ctx.currentTime;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(280, now);
      osc.frequency.exponentialRampToValueAtTime(110, now + 0.25);
      gain.gain.setValueAtTime(0.15, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.28);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(now);
      osc.stop(now + 0.28);
    } catch {}
  }

  playPanic() {
    if (!this.enabled) return;
    try {
      this.init();
      if (!this.ctx) return;
      for (let i = 0; i < 3; i++) {
        const now = this.ctx.currentTime + i * 0.07;
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.type = 'square';
        osc.frequency.setValueAtTime(800, now);
        osc.frequency.setValueAtTime(500, now + 0.035);
        gain.gain.setValueAtTime(0.18, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.065);
        osc.connect(gain);
        gain.connect(this.ctx.destination);
        osc.start(now);
        osc.stop(now + 0.065);
      }
    } catch {}
  }
}

const sounds = new SoundManager();

// --- Types ---
type LogLevel = 'approved' | 'danger' | 'warning' | 'info';

interface TerminalLog {
  id: string;
  timestamp: string;
  source: 'dexscreener' | 'pumpfun';
  level: LogLevel;
  tag: string;
  message: string;
  ticker?: string;
  ca?: string;
  details?: Record<string, string | number>;
}

interface ActivePosition {
  tokenName: string;
  ticker: string;
  ca: string;
  entryPriceSOL: number;
  currentPriceSOL: number;
  entrySizeSOL: number;
  entryTime: number;
  highestPriceSOL: number;
  solPriceUSD: number;
  stagnationSeconds: number;
  maxStagnationSeconds: number;
  breakevenTriggered: boolean;
  trailingStopActive: boolean;
  trailingStopPriceSOL: number;
  priceHistory: { time: number; price: number; pnl: number }[];
}

interface DiscoveredToken {
  id: string;
  ticker: string;
  name: string;
  ca: string;
  marketCapUSD: number;
  vol5mUSD: number;
  liquidityUSD: number;
  bondingCurveProgress: number; // 0 - 100%
  rugcheckScore: number; // 0 (safest) to 500
  top10Concentration: number; // %
  devBoughtSOL: number;
  discoveredAt: string;
  twitter?: string;
  telegram?: string;
  website?: string;
}

export type ExitReason = 'TAKE_PROFIT' | 'STOP_LOSS' | 'TRAILING_STOP' | 'STAGNATION' | 'PANIC_SELL';

export interface ExecutedTrade {
  id: string;
  symbol: string;
  tokenName: string;
  ca: string;
  entryPriceSOL: number;
  exitPriceSOL: number;
  entrySizeSOL: number;
  exitValueSOL: number;
  pnlPct: number;
  pnlSOL: number;
  durationSeconds: number;
  exitType: ExitReason;
  timestamp: string;
}

interface BotSettings {
  tradeSizeSOL: number;
  slippageBps: number;
  takeProfitPct: number;
  stopLossPct: number;
  breakevenTriggerPct: number;
  breakevenFloorPct: number;
  trailingStopTriggerPct: number;
  trailingStopDropPct: number;
  stagnationLimitSec: number;
  requireTwitter: boolean;
  requireTelegram: boolean;
  requireWebsite: boolean;
  maxHolderPct: number;
  maxTop10Pct: number;
  minLiquidityUSD: number;
  jitoTipSOL: number;
}

const DEFAULT_SETTINGS: BotSettings = {
  tradeSizeSOL: 0.02,
  slippageBps: 500, // 5%
  takeProfitPct: 25.0,
  stopLossPct: -10.0,
  breakevenTriggerPct: 5.0,
  breakevenFloorPct: 0.5,
  trailingStopTriggerPct: 8.0,
  trailingStopDropPct: 3.5,
  stagnationLimitSec: 240,
  requireTwitter: true,
  requireTelegram: true,
  requireWebsite: false,
  maxHolderPct: 10.0,
  maxTop10Pct: 25.0,
  minLiquidityUSD: 5000,
  jitoTipSOL: 0.002
};

export default function App() {
  // --- Bot Runtime State ---
  const [botMode, setBotMode] = useState<'RUNNING' | 'PAUSED' | 'PAPER'>('RUNNING');
  const [soundEnabled, setSoundEnabled] = useState<boolean>(true);
  const [simSpeed, setSimSpeed] = useState<number>(1); // 1x, 2x, 5x, 10x
  const [simPaused, setSimPaused] = useState<boolean>(false);
  const [rpcLatency, setRpcLatency] = useState<number>(38);
  const [activeRpc, setActiveRpc] = useState<string>('Helius Mainnet (Dedicated)');
  const [solBalance, setSolBalance] = useState<number>(0.1500);
  const [sessionWins, setSessionWins] = useState<number>(9);
  const [sessionLosses, setSessionLosses] = useState<number>(2);
  const [sessionPnLSOL, setSessionPnLSOL] = useState<number>(0.428);

  // --- Settings Drawer / Export Modal ---
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);
  const [isExportOpen, setIsExportOpen] = useState<boolean>(false);
  const [settings, setSettings] = useState<BotSettings>(DEFAULT_SETTINGS);
  const [copiedToast, setCopiedToast] = useState<string | null>(null);

  // --- Executed Trades History State ---
  const [executedTrades, setExecutedTrades] = useState<ExecutedTrade[]>([
    {
      id: 'tr_1',
      symbol: '$CHILLSOL',
      tokenName: 'Chill Guy Solana',
      ca: '9k3vQ189nBfCqRzW937vKL77m5A3aM1XfK84bL2aL2x',
      entryPriceSOL: 0.00000380,
      exitPriceSOL: 0.00000475,
      entrySizeSOL: 0.0200,
      exitValueSOL: 0.0250,
      pnlPct: 25.0,
      pnlSOL: 0.0050,
      durationSeconds: 102,
      exitType: 'TAKE_PROFIT',
      timestamp: '00:44:18'
    },
    {
      id: 'tr_2',
      symbol: '$TURBOAI',
      tokenName: 'Turbo Neural Matrix',
      ca: '4p2mL892QpBnR9K22vV8M912PzX7411QaN3029kLp22m',
      entryPriceSOL: 0.00000610,
      exitPriceSOL: 0.00000672,
      entrySizeSOL: 0.0200,
      exitValueSOL: 0.0220,
      pnlPct: 10.16,
      pnlSOL: 0.0020,
      durationSeconds: 68,
      exitType: 'TRAILING_STOP',
      timestamp: '00:41:05'
    },
    {
      id: 'tr_3',
      symbol: '$DOGEMATRIX',
      tokenName: 'Doge Quantum Matrix',
      ca: '3b7Xk9912048AzPmK81023J9823901LkzMqp01238910',
      entryPriceSOL: 0.00000520,
      exitPriceSOL: 0.00000468,
      entrySizeSOL: 0.0200,
      exitValueSOL: 0.0180,
      pnlPct: -10.0,
      pnlSOL: -0.0020,
      durationSeconds: 34,
      exitType: 'STOP_LOSS',
      timestamp: '00:38:52'
    },
    {
      id: 'tr_4',
      symbol: '$MEMEX',
      tokenName: 'Meme Exchange Protocol',
      ca: '7v4Y189nBfCqRzW937vKL77m5A3aM1XfK84bL2Piv3',
      entryPriceSOL: 0.00000290,
      exitPriceSOL: 0.00000331,
      entrySizeSOL: 0.0200,
      exitValueSOL: 0.0228,
      pnlPct: 14.14,
      pnlSOL: 0.0028,
      durationSeconds: 135,
      exitType: 'TRAILING_STOP',
      timestamp: '00:34:10'
    },
    {
      id: 'tr_5',
      symbol: '$FARTCOIN',
      tokenName: 'Fartcoin Terminal AI',
      ca: 'Fm331908234857219904234589213457891234789012',
      entryPriceSOL: 0.00000840,
      exitPriceSOL: 0.00000811,
      entrySizeSOL: 0.0200,
      exitValueSOL: 0.0193,
      pnlPct: -3.45,
      pnlSOL: -0.0007,
      durationSeconds: 240,
      exitType: 'STAGNATION',
      timestamp: '00:29:40'
    }
  ]);
  const [tradesSearch, setTradesSearch] = useState<string>('');
  const [tradesOutcomeFilter, setTradesOutcomeFilter] = useState<'ALL' | 'WINS' | 'LOSSES' | 'TP' | 'SL' | 'PANIC'>('ALL');

  // --- Toast notification system ---
  const showToast = (msg: string) => {
    setCopiedToast(msg);
    setTimeout(() => setCopiedToast(null), 2500);
  };

  // --- Active Scalp Position ---
  const [position, setPosition] = useState<ActivePosition | null>({
    tokenName: 'GigaChad Quant AI',
    ticker: '$GIGAQUANT',
    ca: '7v4Y189nBfCqRzW937vKL77m5A3aM1XfK84bL2Piv3',
    entryPriceSOL: 0.00000420,
    currentPriceSOL: 0.00000481,
    entrySizeSOL: 0.0200,
    entryTime: Date.now() - 48000,
    highestPriceSOL: 0.00000495,
    solPriceUSD: 175.40,
    stagnationSeconds: 48,
    maxStagnationSeconds: 240,
    breakevenTriggered: true,
    trailingStopActive: true,
    trailingStopPriceSOL: 0.00000477,
    priceHistory: [
      { time: 1, price: 0.00000420, pnl: 0 },
      { time: 2, price: 0.00000428, pnl: 1.9 },
      { time: 3, price: 0.00000441, pnl: 5.0 },
      { time: 4, price: 0.00000458, pnl: 9.0 },
      { time: 5, price: 0.00000472, pnl: 12.3 },
      { time: 6, price: 0.00000495, pnl: 17.8 },
      { time: 7, price: 0.00000481, pnl: 14.5 }
    ]
  });

  // --- Dual Log Streams ---
  const [dexLogs, setDexLogs] = useState<TerminalLog[]>([
    {
      id: 'd1',
      timestamp: '00:46:12.104',
      source: 'dexscreener',
      level: 'info',
      tag: 'SCANNER_INIT',
      message: 'DexScreener WebSocket listener online. Tracking Raydium & Meteora pair pool creations.'
    },
    {
      id: 'd2',
      timestamp: '00:46:28.419',
      source: 'dexscreener',
      level: 'info',
      tag: 'BATCH_EVAL',
      message: 'Scanned 64 pairs. 59 rejected (Liquidity < $5K), 3 flagged dev bundled snipes.',
      details: { scanned: 64, rejected: 59, eligible: 2 }
    },
    {
      id: 'd3',
      timestamp: '00:46:39.812',
      source: 'dexscreener',
      level: 'warning',
      tag: 'VOL_SPIKE',
      message: '$CHILLSOL 5m volume spike $38.4K (312 txs). High buy pressure (78% buy ratio).',
      ticker: '$CHILLSOL',
      ca: '9k3v...aL2x'
    },
    {
      id: 'd4',
      timestamp: '00:46:48.210',
      source: 'dexscreener',
      level: 'approved',
      tag: 'QUALIFIED_PAIR',
      message: '$GIGAQUANT verified: Liquidity $18.4K, 5m Vol $52.1K, Top 10 non-LP concentration 11.2%. Met scalp criteria.',
      ticker: '$GIGAQUANT',
      ca: '7v4Y...Piv3'
    }
  ]);

  const [pumpLogs, setPumpLogs] = useState<TerminalLog[]>([
    {
      id: 'p1',
      timestamp: '00:46:09.002',
      source: 'pumpfun',
      level: 'info',
      tag: 'WS_SUBSCRIBED',
      message: 'Subscribed to PumpPortal WebSocket feed. Zero-delay raw block stream armed.'
    },
    {
      id: 'p2',
      timestamp: '00:46:18.520',
      source: 'pumpfun',
      level: 'danger',
      tag: 'CABAL_DETECTED',
      message: 'Mint 4f8K... rejected: Dev bundled 38.4% supply across 14 multi-sig addresses. Immediate Blacklist.',
      ticker: '$SCAMCAT',
      ca: '4f8K...22pL'
    },
    {
      id: 'p3',
      timestamp: '00:46:31.114',
      source: 'pumpfun',
      level: 'info',
      tag: 'OSINT_AUDIT',
      message: 'IPFS metadata parsed: Twitter @pepeai_sol (Age: 320d, 8.4k followers). Bio & banner matching.',
      ticker: '$PEPEAI'
    },
    {
      id: 'p4',
      timestamp: '00:46:42.780',
      source: 'pumpfun',
      level: 'approved',
      tag: 'SNIPER_ARMED',
      message: 'New mint: $GIGAQUANT. Dev bought 3.2 SOL (5.1% supply). RugCheck 0/500 Low Risk. Bonding curve: 18.2%.',
      ticker: '$GIGAQUANT',
      ca: '7v4Y...Piv3'
    }
  ]);

  // Terminal scroll & search controls
  const [dexAutoScroll, setDexAutoScroll] = useState<boolean>(true);
  const [pumpAutoScroll, setPumpAutoScroll] = useState<boolean>(true);
  const [dexFilter, setDexFilter] = useState<string>('');
  const [pumpFilter, setPumpFilter] = useState<string>('');
  const [dexLevelFilter, setDexLevelFilter] = useState<string>('ALL');
  const [pumpLevelFilter, setPumpLevelFilter] = useState<string>('ALL');

  const dexScrollRef = useRef<HTMLDivElement>(null);
  const pumpScrollRef = useRef<HTMLDivElement>(null);

  // Discovered tokens feed
  const [discoveredTokens, setDiscoveredTokens] = useState<DiscoveredToken[]>([
    {
      id: 't1',
      ticker: '$GIGAQUANT',
      name: 'GigaChad Quant AI',
      ca: '7v4Y189nBfCqRzW937vKL77m5A3aM1XfK84bL2Piv3',
      marketCapUSD: 48200,
      vol5mUSD: 52100,
      liquidityUSD: 18400,
      bondingCurveProgress: 42.5,
      rugcheckScore: 0,
      top10Concentration: 11.2,
      devBoughtSOL: 3.2,
      discoveredAt: '1m ago',
      twitter: 'https://twitter.com/gigaquant_ai',
      telegram: 'https://t.me/gigaquant_ai',
      website: 'https://gigaquant.sol'
    },
    {
      id: 't2',
      ticker: '$PEPEAI',
      name: 'Pepe Neuro Matrix',
      ca: '8xLm492QpBnR9K22vV8M912PzX7411QaN3029kLp1024',
      marketCapUSD: 36800,
      vol5mUSD: 41200,
      liquidityUSD: 14200,
      bondingCurveProgress: 31.0,
      rugcheckScore: 15,
      top10Concentration: 14.8,
      devBoughtSOL: 2.5,
      discoveredAt: '3m ago',
      twitter: 'https://twitter.com/pepenatrix_sol',
      telegram: 'https://t.me/pepenatrix_sol'
    },
    {
      id: 't3',
      ticker: '$SOLPUMP',
      name: 'Solana Speed Velocity',
      ca: '3b7Xk9912048AzPmK81023J9823901LkzMqp01238910',
      marketCapUSD: 72400,
      vol5mUSD: 89500,
      liquidityUSD: 24900,
      bondingCurveProgress: 68.4,
      rugcheckScore: 0,
      top10Concentration: 9.6,
      devBoughtSOL: 4.8,
      discoveredAt: '6m ago',
      twitter: 'https://twitter.com/solpump_speed',
      website: 'https://solpump.speed'
    },
    {
      id: 't4',
      ticker: '$CATWIF',
      name: 'Cyber Cat Hat',
      ca: 'Fm331908234857219904234589213457891234789012',
      marketCapUSD: 22100,
      vol5mUSD: 28400,
      liquidityUSD: 11800,
      bondingCurveProgress: 19.8,
      rugcheckScore: 20,
      top10Concentration: 16.1,
      devBoughtSOL: 1.8,
      discoveredAt: '9m ago',
      telegram: 'https://t.me/cybercathat'
    }
  ]);

  // Sync sound settings with SoundManager
  useEffect(() => {
    sounds.enabled = soundEnabled;
  }, [soundEnabled]);

  // Handle sticky scrolling for DexScreener logs
  useEffect(() => {
    if (dexAutoScroll && dexScrollRef.current) {
      dexScrollRef.current.scrollTop = dexScrollRef.current.scrollHeight;
    }
  }, [dexLogs, dexAutoScroll]);

  // Handle sticky scrolling for Pump.fun logs
  useEffect(() => {
    if (pumpAutoScroll && pumpScrollRef.current) {
      pumpScrollRef.current.scrollTop = pumpScrollRef.current.scrollHeight;
    }
  }, [pumpLogs, pumpAutoScroll]);

  // Format timestamp helper
  const nowTimestamp = () => {
    const d = new Date();
    const pad = (n: number, z = 2) => String(n).padStart(z, '0');
    return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${pad(d.getMilliseconds(), 3)}`;
  };

  // --- Real-time Mock Simulation Engine ---
  useEffect(() => {
    if (simPaused || botMode === 'PAUSED') return;

    const baseInterval = 1200 / simSpeed;

    const simTimer = setInterval(() => {
      // 1. Tick Active Position Price if open
      setPosition((prev) => {
        if (!prev) return null;

        // Random walk with positive drift
        const delta = (Math.random() - 0.46) * 0.00000008;
        const newPrice = Math.max(0.000001, prev.currentPriceSOL + delta);
        const pnlPct = ((newPrice - prev.entryPriceSOL) / prev.entryPriceSOL) * 100;
        const newHighest = Math.max(prev.highestPriceSOL, newPrice);
        const newStagnation = prev.stagnationSeconds + 1;

        // Strategy Triggers:
        let breakevenTriggered = prev.breakevenTriggered;
        let trailingActive = prev.trailingStopActive;
        let trailingStopPrice = prev.trailingStopPriceSOL;

        // Breakeven check (+5% trigger -> locks floor at +0.5%)
        if (!breakevenTriggered && pnlPct >= settings.breakevenTriggerPct) {
          breakevenTriggered = true;
          trailingStopPrice = prev.entryPriceSOL * (1 + settings.breakevenFloorPct / 100);
          showToast(`🛡️ Breakeven Floor Activated for ${prev.ticker} (+0.5% locked)`);
        }

        // Trailing Stop (+8% trigger, 3.5% drop from high water mark)
        if (pnlPct >= settings.trailingStopTriggerPct) {
          trailingActive = true;
          const calculatedTrailing = newHighest * (1 - settings.trailingStopDropPct / 100);
          trailingStopPrice = Math.max(trailingStopPrice, calculatedTrailing);
        }

        // Hard Take Profit (+25%)
        if (pnlPct >= settings.takeProfitPct) {
          sounds.playTakeProfit();
          showToast(`🎉 TAKE PROFIT HIT: ${prev.ticker} at +${pnlPct.toFixed(1)}%! Executing Sell...`);
          // Record win
          setSessionWins((w) => w + 1);
          const profitSOL = prev.entrySizeSOL * (pnlPct / 100);
          setSessionPnLSOL((p) => p + profitSOL);
          setSolBalance((b) => b + prev.entrySizeSOL + profitSOL);
          const closedTrade: ExecutedTrade = {
            id: 'tr_' + Date.now(),
            symbol: prev.ticker,
            tokenName: prev.tokenName,
            ca: prev.ca,
            entryPriceSOL: prev.entryPriceSOL,
            exitPriceSOL: newPrice,
            entrySizeSOL: prev.entrySizeSOL,
            exitValueSOL: prev.entrySizeSOL + profitSOL,
            pnlPct: pnlPct,
            pnlSOL: profitSOL,
            durationSeconds: newStagnation,
            exitType: 'TAKE_PROFIT',
            timestamp: nowTimestamp().split('.')[0]
          };
          setExecutedTrades((t) => [closedTrade, ...t]);
          return null; // Position closed
        }

        // Hard Stop Loss (-10%) or Trailing Stop Trigger
        if (pnlPct <= settings.stopLossPct) {
          sounds.playStopLoss();
          showToast(`🛑 STOP LOSS HIT: ${prev.ticker} at ${pnlPct.toFixed(1)}%! Exited.`);
          setSessionLosses((l) => l + 1);
          const lossSOL = prev.entrySizeSOL * (pnlPct / 100);
          setSessionPnLSOL((p) => p + lossSOL);
          setSolBalance((b) => b + prev.entrySizeSOL + lossSOL);
          const closedTrade: ExecutedTrade = {
            id: 'tr_' + Date.now(),
            symbol: prev.ticker,
            tokenName: prev.tokenName,
            ca: prev.ca,
            entryPriceSOL: prev.entryPriceSOL,
            exitPriceSOL: newPrice,
            entrySizeSOL: prev.entrySizeSOL,
            exitValueSOL: prev.entrySizeSOL + lossSOL,
            pnlPct: pnlPct,
            pnlSOL: lossSOL,
            durationSeconds: newStagnation,
            exitType: 'STOP_LOSS',
            timestamp: nowTimestamp().split('.')[0]
          };
          setExecutedTrades((t) => [closedTrade, ...t]);
          return null;
        }

        if (trailingActive && newPrice <= trailingStopPrice && trailingStopPrice > 0) {
          sounds.playTakeProfit();
          showToast(`🚀 TRAILING STOP TRIGGERED: ${prev.ticker} locked gains at +${pnlPct.toFixed(1)}%!`);
          setSessionWins((w) => w + 1);
          const profitSOL = prev.entrySizeSOL * (pnlPct / 100);
          setSessionPnLSOL((p) => p + profitSOL);
          setSolBalance((b) => b + prev.entrySizeSOL + profitSOL);
          const closedTrade: ExecutedTrade = {
            id: 'tr_' + Date.now(),
            symbol: prev.ticker,
            tokenName: prev.tokenName,
            ca: prev.ca,
            entryPriceSOL: prev.entryPriceSOL,
            exitPriceSOL: newPrice,
            entrySizeSOL: prev.entrySizeSOL,
            exitValueSOL: prev.entrySizeSOL + profitSOL,
            pnlPct: pnlPct,
            pnlSOL: profitSOL,
            durationSeconds: newStagnation,
            exitType: 'TRAILING_STOP',
            timestamp: nowTimestamp().split('.')[0]
          };
          setExecutedTrades((t) => [closedTrade, ...t]);
          return null;
        }

        // Stagnation Timeout (240s)
        if (newStagnation >= settings.stagnationLimitSec) {
          sounds.playStopLoss();
          showToast(`⌛ STAGNATION TIMEOUT (240s): Market selling ${prev.ticker}`);
          const pnlSOL = prev.entrySizeSOL * (pnlPct / 100);
          if (pnlPct >= 0) setSessionWins((w) => w + 1);
          else setSessionLosses((l) => l + 1);
          setSessionPnLSOL((p) => p + pnlSOL);
          setSolBalance((b) => b + prev.entrySizeSOL + pnlSOL);
          const closedTrade: ExecutedTrade = {
            id: 'tr_' + Date.now(),
            symbol: prev.ticker,
            tokenName: prev.tokenName,
            ca: prev.ca,
            entryPriceSOL: prev.entryPriceSOL,
            exitPriceSOL: newPrice,
            entrySizeSOL: prev.entrySizeSOL,
            exitValueSOL: prev.entrySizeSOL + pnlSOL,
            pnlPct: pnlPct,
            pnlSOL: pnlSOL,
            durationSeconds: newStagnation,
            exitType: 'STAGNATION',
            timestamp: nowTimestamp().split('.')[0]
          };
          setExecutedTrades((t) => [closedTrade, ...t]);
          return null;
        }

        const newHistory = [
          ...prev.priceHistory.slice(-18),
          { time: Date.now(), price: newPrice, pnl: pnlPct }
        ];

        return {
          ...prev,
          currentPriceSOL: newPrice,
          highestPriceSOL: newHighest,
          stagnationSeconds: newStagnation,
          breakevenTriggered,
          trailingStopActive: trailingActive,
          trailingStopPriceSOL: trailingStopPrice,
          priceHistory: newHistory
        };
      });

      // 2. Randomly jitter RPC latency
      setRpcLatency(Math.floor(32 + Math.random() * 18));

      // 3. Generate Random DexScreener & Pump.fun events occasionally
      const roll = Math.random();
      const sampleTickers = ['$NEURAL', '$MEMEX', '$DOGEAI', '$SOLPEPE', '$TURBO', '$FARTCOIN', '$CHILLCAT', '$SOLMAX'];
      const chosenTicker = sampleTickers[Math.floor(Math.random() * sampleTickers.length)];
      const randomCA = `${Math.random().toString(36).substring(2, 6)}...${Math.random().toString(36).substring(2, 6)}`;

      if (roll < 0.35) {
        // DexScreener batch evaluation
        const scanned = Math.floor(30 + Math.random() * 40);
        const rejected = scanned - Math.floor(Math.random() * 3);
        const newDexLog: TerminalLog = {
          id: 'dex_' + Date.now(),
          timestamp: nowTimestamp(),
          source: 'dexscreener',
          level: 'info',
          tag: 'BATCH_EVAL',
          message: `Batch #${Math.floor(1000 + Math.random() * 9000)}: Scanned ${scanned} pool pairs. ${rejected} rejected (Low Liq / Dev concentration).`
        };
        setDexLogs((prev) => [...prev.slice(-120), newDexLog]);
      } else if (roll < 0.65) {
        // Pump.fun Mint / OSINT
        const isRug = Math.random() < 0.3;
        const newPumpLog: TerminalLog = {
          id: 'pf_' + Date.now(),
          timestamp: nowTimestamp(),
          source: 'pumpfun',
          level: isRug ? 'danger' : 'info',
          tag: isRug ? 'CABAL_ALERT' : 'WS_MINT',
          message: isRug
            ? `Mint ${randomCA} (${chosenTicker}) flagged: dev wallet held 41.2% in cluster. Aborting snipe.`
            : `New block sub-second mint: ${chosenTicker} (${randomCA}). Dev bought 2.8 SOL. Bonding curve 4.1%.`,
          ticker: chosenTicker,
          ca: randomCA
        };
        setPumpLogs((prev) => [...prev.slice(-120), newPumpLog]);
      } else if (roll > 0.88) {
        // Approved token found!
        const approvedDex: TerminalLog = {
          id: 'dex_app_' + Date.now(),
          timestamp: nowTimestamp(),
          source: 'dexscreener',
          level: 'approved',
          tag: 'QUALIFIED_MOMENTUM',
          message: `${chosenTicker} met all momentum hurdles: 5m Vol > $35K, Buyer Ratio 82%, RugCheck 0/500 safe.`,
          ticker: chosenTicker,
          ca: randomCA
        };
        const approvedPump: TerminalLog = {
          id: 'pf_app_' + Date.now(),
          timestamp: nowTimestamp(),
          source: 'pumpfun',
          level: 'approved',
          tag: 'DEV_VERIFIED',
          message: `${chosenTicker} socials verified: Twitter age > 180d, Telegram group non-botted. On-chain non-LP 12.1%.`,
          ticker: chosenTicker,
          ca: randomCA
        };
        setDexLogs((prev) => [...prev.slice(-120), approvedDex]);
        setPumpLogs((prev) => [...prev.slice(-120), approvedPump]);

        // Add to discovered tokens
        setDiscoveredTokens((prev) => [
          {
            id: 'tok_' + Date.now(),
            ticker: chosenTicker,
            name: `${chosenTicker.replace('$', '')} AI Protocol`,
            ca: `${randomCA.replace('...', '7xK92bA1')}`,
            marketCapUSD: Math.floor(25000 + Math.random() * 45000),
            vol5mUSD: Math.floor(30000 + Math.random() * 50000),
            liquidityUSD: Math.floor(12000 + Math.random() * 15000),
            bondingCurveProgress: Math.floor(15 + Math.random() * 55),
            rugcheckScore: Math.floor(Math.random() * 20),
            top10Concentration: +(10 + Math.random() * 8).toFixed(1),
            devBoughtSOL: +(1.5 + Math.random() * 3).toFixed(1),
            discoveredAt: 'Just now',
            twitter: `https://twitter.com/${chosenTicker.replace('$', '').toLowerCase()}_sol`,
            telegram: `https://t.me/${chosenTicker.replace('$', '').toLowerCase()}_sol`
          },
          ...prev.slice(0, 7)
        ]);
      }
    }, baseInterval);

    return () => clearInterval(simTimer);
  }, [simPaused, botMode, simSpeed, settings]);

  // --- Manual Actions ---
  const handlePanicSell = () => {
    if (!position) return;
    sounds.playPanic();
    const pnlPct = ((position.currentPriceSOL - position.entryPriceSOL) / position.entryPriceSOL) * 100;
    const pnlSOL = position.entrySizeSOL * (pnlPct / 100);
    showToast(`🚨 EMERGENCY MARKET SELL EXECUTED! Exited 100% at ${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(1)}%`);

    if (pnlPct >= 0) {
      setSessionWins((w) => w + 1);
    } else {
      setSessionLosses((l) => l + 1);
    }
    setSessionPnLSOL((p) => p + pnlSOL);
    setSolBalance((b) => b + position.entrySizeSOL + pnlSOL);

    const closedTrade: ExecutedTrade = {
      id: 'tr_' + Date.now(),
      symbol: position.ticker,
      tokenName: position.tokenName,
      ca: position.ca,
      entryPriceSOL: position.entryPriceSOL,
      exitPriceSOL: position.currentPriceSOL,
      entrySizeSOL: position.entrySizeSOL,
      exitValueSOL: position.entrySizeSOL + pnlSOL,
      pnlPct: pnlPct,
      pnlSOL: pnlSOL,
      durationSeconds: position.stagnationSeconds,
      exitType: 'PANIC_SELL',
      timestamp: nowTimestamp().split('.')[0]
    };
    setExecutedTrades((t) => [closedTrade, ...t]);

    // Append panic log to both streams
    const panicLog: TerminalLog = {
      id: 'panic_' + Date.now(),
      timestamp: nowTimestamp(),
      source: 'pumpfun',
      level: 'danger',
      tag: 'PANIC_SELL',
      message: `USER TRIGGERED EMERGENCY 100% EXIT on ${position.ticker}. Jito Tip: 0.005 SOL priority fill.`,
      ticker: position.ticker
    };
    setPumpLogs((prev) => [...prev, panicLog]);
    setPosition(null);
  };

  const handleManualScalp = (token: DiscoveredToken) => {
    if (position) {
      showToast(`⚠️ An active position is already open for ${position.ticker}. Close it first!`);
      return;
    }
    sounds.playBuy();
    const entryPrice = 0.00000400 + Math.random() * 0.00000100;
    setPosition({
      tokenName: token.name,
      ticker: token.ticker,
      ca: token.ca,
      entryPriceSOL: entryPrice,
      currentPriceSOL: entryPrice,
      entrySizeSOL: settings.tradeSizeSOL,
      entryTime: Date.now(),
      highestPriceSOL: entryPrice,
      solPriceUSD: 175.40,
      stagnationSeconds: 0,
      maxStagnationSeconds: settings.stagnationLimitSec,
      breakevenTriggered: false,
      trailingStopActive: false,
      trailingStopPriceSOL: 0,
      priceHistory: [{ time: Date.now(), price: entryPrice, pnl: 0 }]
    });

    setSolBalance((b) => Math.max(0.01, b - settings.tradeSizeSOL - settings.jitoTipSOL));
    showToast(`🚀 Scalp Entered: ${token.ticker} for ${settings.tradeSizeSOL} SOL`);

    const buyLog: TerminalLog = {
      id: 'buy_' + Date.now(),
      timestamp: nowTimestamp(),
      source: 'pumpfun',
      level: 'approved',
      tag: 'MANUAL_ENTRY',
      message: `Order submitted: Bought ${settings.tradeSizeSOL} SOL of ${token.ticker} via Jito MEV Bundle.`,
      ticker: token.ticker,
      ca: token.ca
    };
    setPumpLogs((prev) => [...prev, buyLog]);
  };

  const handleTriggerFakePump = () => {
    if (!position) {
      showToast('⚠️ Open an active trade first to test price pump!');
      return;
    }
    sounds.playTakeProfit();
    setPosition((prev) => {
      if (!prev) return null;
      const pumped = prev.currentPriceSOL * 1.15;
      const pnlPct = ((pumped - prev.entryPriceSOL) / prev.entryPriceSOL) * 100;
      return {
        ...prev,
        currentPriceSOL: pumped,
        highestPriceSOL: Math.max(prev.highestPriceSOL, pumped),
        priceHistory: [...prev.priceHistory, { time: Date.now(), price: pumped, pnl: pnlPct }]
      };
    });
    showToast(`⚡ Injected +15% Price Spike into ${position.ticker}!`);
  };

  const handleTriggerFakeDump = () => {
    if (!position) {
      showToast('⚠️ Open an active trade first to test price dump!');
      return;
    }
    sounds.playStopLoss();
    setPosition((prev) => {
      if (!prev) return null;
      const dumped = prev.currentPriceSOL * 0.88;
      const pnlPct = ((dumped - prev.entryPriceSOL) / prev.entryPriceSOL) * 100;
      return {
        ...prev,
        currentPriceSOL: dumped,
        priceHistory: [...prev.priceHistory, { time: Date.now(), price: dumped, pnl: pnlPct }]
      };
    });
    showToast(`🔻 Injected -12% Dump into ${position.ticker}!`);
  };

  // --- Filtered Logs ---
  const filteredDexLogs = useMemo(() => {
    return dexLogs.filter((log) => {
      const matchSearch =
        dexFilter.trim() === '' ||
        log.message.toLowerCase().includes(dexFilter.toLowerCase()) ||
        log.tag.toLowerCase().includes(dexFilter.toLowerCase()) ||
        (log.ticker && log.ticker.toLowerCase().includes(dexFilter.toLowerCase())) ||
        (log.ca && log.ca.toLowerCase().includes(dexFilter.toLowerCase()));
      const matchLevel = dexLevelFilter === 'ALL' || log.level.toUpperCase() === dexLevelFilter;
      return matchSearch && matchLevel;
    });
  }, [dexLogs, dexFilter, dexLevelFilter]);

  const filteredPumpLogs = useMemo(() => {
    return pumpLogs.filter((log) => {
      const matchSearch =
        pumpFilter.trim() === '' ||
        log.message.toLowerCase().includes(pumpFilter.toLowerCase()) ||
        log.tag.toLowerCase().includes(pumpFilter.toLowerCase()) ||
        (log.ticker && log.ticker.toLowerCase().includes(pumpFilter.toLowerCase())) ||
        (log.ca && log.ca.toLowerCase().includes(pumpFilter.toLowerCase()));
      const matchLevel = pumpLevelFilter === 'ALL' || log.level.toUpperCase() === pumpLevelFilter;
      return matchSearch && matchLevel;
    });
  }, [pumpLogs, pumpFilter, pumpLevelFilter]);

  const copyToClipboard = (text: string, label: string) => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text);
      showToast(`Copied ${label} to clipboard!`);
    }
  };

  // --- Net PnL calculations ---
  const currentPnLPct = position
    ? ((position.currentPriceSOL - position.entryPriceSOL) / position.entryPriceSOL) * 100
    : 0;
  const currentExitValueSOL = position
    ? position.entrySizeSOL * (1 + currentPnLPct / 100)
    : 0;
  const currentNetProfitSOL = position
    ? currentExitValueSOL - position.entrySizeSOL
    : 0;

  // Stagnation percentage
  const stagnationPercent = position
    ? Math.min(100, (position.stagnationSeconds / position.maxStagnationSeconds) * 100)
    : 0;

  // Format Duration Helper
  const formatDuration = (sec: number) => {
    if (sec < 60) return `${sec}s`;
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}m ${s.toString().padStart(2, '0')}s`;
  };

  // Helper for Exit Type Badges
  const getExitTypeInfo = (exitType: ExitReason) => {
    switch (exitType) {
      case 'TAKE_PROFIT':
        return {
          label: 'Hard Take Profit (+25%)',
          badgeClass: 'bg-emerald-950/70 border-emerald-500/40 text-emerald-300',
          dotClass: 'bg-emerald-400'
        };
      case 'TRAILING_STOP':
        return {
          label: 'Trailing Stop Locked',
          badgeClass: 'bg-purple-950/70 border-purple-500/40 text-purple-300',
          dotClass: 'bg-purple-400'
        };
      case 'STOP_LOSS':
        return {
          label: 'Hard Stop Loss (-10%)',
          badgeClass: 'bg-red-950/70 border-red-500/40 text-red-300',
          dotClass: 'bg-red-400'
        };
      case 'STAGNATION':
        return {
          label: 'Stagnation Timeout (240s)',
          badgeClass: 'bg-amber-950/70 border-amber-500/40 text-amber-300',
          dotClass: 'bg-amber-400'
        };
      case 'PANIC_SELL':
        return {
          label: 'Emergency Market Sell',
          badgeClass: 'bg-rose-950/70 border-rose-500/40 text-rose-300',
          dotClass: 'bg-rose-400'
        };
      default:
        return {
          label: exitType,
          badgeClass: 'bg-slate-900 border-white/10 text-slate-300',
          dotClass: 'bg-slate-400'
        };
    }
  };

  // Filtered Executed Trades
  const filteredExecutedTrades = useMemo(() => {
    return executedTrades.filter((trade) => {
      const q = tradesSearch.trim().toLowerCase();
      const matchSearch =
        q === '' ||
        trade.symbol.toLowerCase().includes(q) ||
        trade.tokenName.toLowerCase().includes(q) ||
        trade.ca.toLowerCase().includes(q);

      let matchOutcome = true;
      if (tradesOutcomeFilter === 'WINS') matchOutcome = trade.pnlSOL > 0;
      else if (tradesOutcomeFilter === 'LOSSES') matchOutcome = trade.pnlSOL < 0;
      else if (tradesOutcomeFilter === 'TP') matchOutcome = trade.exitType === 'TAKE_PROFIT';
      else if (tradesOutcomeFilter === 'SL') matchOutcome = trade.exitType === 'STOP_LOSS';
      else if (tradesOutcomeFilter === 'PANIC') matchOutcome = trade.exitType === 'PANIC_SELL';

      return matchSearch && matchOutcome;
    });
  }, [executedTrades, tradesSearch, tradesOutcomeFilter]);

  // Aggregate executed trade metrics
  const totalExecutedPnlSOL = useMemo(() => {
    return executedTrades.reduce((acc, t) => acc + t.pnlSOL, 0);
  }, [executedTrades]);

  const totalExecutedWins = useMemo(() => {
    return executedTrades.filter((t) => t.pnlSOL > 0).length;
  }, [executedTrades]);

  const totalExecutedLosses = useMemo(() => {
    return executedTrades.filter((t) => t.pnlSOL < 0).length;
  }, [executedTrades]);

  const avgTradeDurationSec = useMemo(() => {
    if (executedTrades.length === 0) return 0;
    const sum = executedTrades.reduce((acc, t) => acc + t.durationSeconds, 0);
    return Math.round(sum / executedTrades.length);
  }, [executedTrades]);

  const exportTradesCSV = () => {
    if (executedTrades.length === 0) {
      showToast('No executed trades to export');
      return;
    }
    const headers = 'Symbol,Name,CA,EntryPriceSOL,ExitPriceSOL,SizeSOL,ExitValueSOL,PnLPct,PnLSOL,DurationSec,ExitType,Timestamp\n';
    const rows = executedTrades
      .map(
        (t) =>
          `"${t.symbol}","${t.tokenName}","${t.ca}",${t.entryPriceSOL},${t.exitPriceSOL},${t.entrySizeSOL},${t.exitValueSOL},${t.pnlPct.toFixed(2)},${t.pnlSOL.toFixed(6)},${t.durationSeconds},"${t.exitType}","${t.timestamp}"`
      )
      .join('\n');
    const blob = new Blob([headers + rows], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `solana_sniper_executed_trades_${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    showToast('Exported executed trades to CSV!');
  };

  const clearExecutedTrades = () => {
    setExecutedTrades([]);
    showToast('Executed trades history cleared');
  };

  const restoreSampleTrades = () => {
    setExecutedTrades([
      {
        id: 'tr_1',
        symbol: '$CHILLSOL',
        tokenName: 'Chill Guy Solana',
        ca: '9k3vQ189nBfCqRzW937vKL77m5A3aM1XfK84bL2aL2x',
        entryPriceSOL: 0.00000380,
        exitPriceSOL: 0.00000475,
        entrySizeSOL: 0.0200,
        exitValueSOL: 0.0250,
        pnlPct: 25.0,
        pnlSOL: 0.0050,
        durationSeconds: 102,
        exitType: 'TAKE_PROFIT',
        timestamp: '00:44:18'
      },
      {
        id: 'tr_2',
        symbol: '$TURBOAI',
        tokenName: 'Turbo Neural Matrix',
        ca: '4p2mL892QpBnR9K22vV8M912PzX7411QaN3029kLp22m',
        entryPriceSOL: 0.00000610,
        exitPriceSOL: 0.00000672,
        entrySizeSOL: 0.0200,
        exitValueSOL: 0.0220,
        pnlPct: 10.16,
        pnlSOL: 0.0020,
        durationSeconds: 68,
        exitType: 'TRAILING_STOP',
        timestamp: '00:41:05'
      },
      {
        id: 'tr_3',
        symbol: '$DOGEMATRIX',
        tokenName: 'Doge Quantum Matrix',
        ca: '3b7Xk9912048AzPmK81023J9823901LkzMqp01238910',
        entryPriceSOL: 0.00000520,
        exitPriceSOL: 0.00000468,
        entrySizeSOL: 0.0200,
        exitValueSOL: 0.0180,
        pnlPct: -10.0,
        pnlSOL: -0.0020,
        durationSeconds: 34,
        exitType: 'STOP_LOSS',
        timestamp: '00:38:52'
      },
      {
        id: 'tr_4',
        symbol: '$MEMEX',
        tokenName: 'Meme Exchange Protocol',
        ca: '7v4Y189nBfCqRzW937vKL77m5A3aM1XfK84bL2Piv3',
        entryPriceSOL: 0.00000290,
        exitPriceSOL: 0.00000331,
        entrySizeSOL: 0.0200,
        exitValueSOL: 0.0228,
        pnlPct: 14.14,
        pnlSOL: 0.0028,
        durationSeconds: 135,
        exitType: 'TRAILING_STOP',
        timestamp: '00:34:10'
      },
      {
        id: 'tr_5',
        symbol: '$FARTCOIN',
        tokenName: 'Fartcoin Terminal AI',
        ca: 'Fm331908234857219904234589213457891234789012',
        entryPriceSOL: 0.00000840,
        exitPriceSOL: 0.00000811,
        entrySizeSOL: 0.0200,
        exitValueSOL: 0.0193,
        pnlPct: -3.45,
        pnlSOL: -0.0007,
        durationSeconds: 240,
        exitType: 'STAGNATION',
        timestamp: '00:29:40'
      }
    ]);
    showToast('Restored sample executed trades');
  };

  return (
    <div className="min-h-screen bg-[#07090e] bg-terminal-grid text-slate-100 flex flex-col font-sans select-none antialiased">
      {/* Toast Notification */}
      {copiedToast && (
        <div className="fixed top-4 right-4 z-50 bg-slate-900 border border-emerald-500/40 text-emerald-300 px-4 py-2.5 rounded-lg shadow-2xl flex items-center gap-2 text-xs font-mono glow-emerald animate-bounce">
          <Check className="w-4 h-4 text-emerald-400" />
          <span>{copiedToast}</span>
        </div>
      )}

      {/* TOP BAR / CONTROL STATION */}
      <header className="sticky top-0 z-40 bg-[#090c13]/90 backdrop-blur-md border-b border-white/10 px-4 py-2.5 flex flex-wrap items-center justify-between gap-3">
        {/* Brand / Logo */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-purple-600 via-indigo-500 to-emerald-400 flex items-center justify-center p-0.5 shadow-lg">
            <div className="w-full h-full bg-[#090c13] rounded-[6px] flex items-center justify-center">
              <Zap className="w-4 h-4 text-emerald-400" />
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-sm tracking-wider text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 via-cyan-300 to-purple-400">
                SOLANA SNIPER &amp; SCALP BOT
              </span>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                v3.2 HFT
              </span>
            </div>
            <div className="text-[11px] text-slate-400 flex items-center gap-2 font-mono">
              <span>PumpPortal Sub-ms</span>
              <span>·</span>
              <span>DexScreener API v2</span>
              <span>·</span>
              <span>Jito MEV Bundles</span>
            </div>
          </div>
        </div>

        {/* Wallet & Infrastructure Telemetry */}
        <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
          {/* Wallet Address */}
          <div className="flex items-center gap-1.5 bg-slate-900/80 border border-white/10 px-2.5 py-1.5 rounded-md text-slate-300">
            <Wallet className="w-3.5 h-3.5 text-purple-400" />
            <span className="text-slate-400">Wallet:</span>
            <span className="text-slate-200 font-semibold">E6Q4...Piv3</span>
            <button
              onClick={() => copyToClipboard('E6Q4N72xLqZ984Bfv739Piv38KmQpL8240M1928374', 'Wallet Address')}
              className="text-slate-400 hover:text-white transition-colors p-0.5 ml-1"
              title="Copy Public Key"
            >
              <Copy className="w-3 h-3" />
            </button>
            <a
              href="https://solscan.io"
              target="_blank"
              rel="noreferrer"
              className="text-slate-400 hover:text-emerald-400 transition-colors p-0.5"
              title="View on Solscan"
            >
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>

          {/* SOL Balance & Reserve */}
          <div className="flex items-center gap-2 bg-slate-900/80 border border-white/10 px-2.5 py-1.5 rounded-md">
            <span className="text-slate-400">SOL:</span>
            <span className="text-emerald-400 font-bold tabular-nums">
              {solBalance.toFixed(4)} SOL
            </span>
            <span className="text-[10px] text-slate-500 border-l border-white/10 pl-1.5">
              Fee Reserve: 0.04 SOL
            </span>
          </div>

          {/* RPC Latency & Failover */}
          <div className="flex items-center gap-1.5 bg-slate-900/80 border border-white/10 px-2.5 py-1.5 rounded-md">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></div>
            <span className="text-slate-300">{activeRpc}</span>
            <span className="text-emerald-400 font-semibold tabular-nums">({rpcLatency}ms)</span>
          </div>

          {/* Bot Mode Segmented Toggle */}
          <div className="flex items-center p-0.5 bg-slate-950 border border-white/10 rounded-md">
            <button
              onClick={() => {
                setBotMode('RUNNING');
                showToast('Bot set to LIVE RUNNING mode');
              }}
              className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-all ${
                botMode === 'RUNNING'
                  ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              RUNNING
            </button>
            <button
              onClick={() => {
                setBotMode('PAUSED');
                showToast('Bot PAUSED (Monitoring only)');
              }}
              className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-all ${
                botMode === 'PAUSED'
                  ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              PAUSED
            </button>
            <button
              onClick={() => {
                setBotMode('PAPER');
                showToast('Switched to PAPER TRADING mode');
              }}
              className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-all ${
                botMode === 'PAPER'
                  ? 'bg-purple-500 text-white shadow-md shadow-purple-500/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              PAPER
            </button>
          </div>

          {/* Audio Sound Toggle */}
          <button
            onClick={() => setSoundEnabled(!soundEnabled)}
            className={`p-1.5 rounded-md border border-white/10 transition-colors ${
              soundEnabled ? 'bg-slate-800 text-emerald-400' : 'bg-slate-900 text-slate-500'
            }`}
            title={soundEnabled ? 'Mute Audio Chimes' : 'Enable Audio Chimes'}
          >
            {soundEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
          </button>

          {/* Settings Drawer Button */}
          <button
            onClick={() => setIsSettingsOpen(true)}
            className="flex items-center gap-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-white/10 px-2.5 py-1.5 rounded-md transition-colors"
          >
            <Sliders className="w-3.5 h-3.5 text-cyan-400" />
            <span>Config</span>
          </button>

          {/* Export Standalone HTML Button */}
          <button
            onClick={() => setIsExportOpen(true)}
            className="flex items-center gap-1.5 bg-gradient-to-r from-purple-700 to-indigo-600 hover:from-purple-600 hover:to-indigo-500 text-white px-2.5 py-1.5 rounded-md shadow-md text-xs font-semibold transition-all"
            title="Export Standalone HTML5 Single-File"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export HTML</span>
          </button>
        </div>
      </header>

      {/* SIMULATOR QUICK BAR & SIMULATION CONTROLS */}
      <div className="bg-[#0b0e16] border-b border-white/10 px-4 py-1.5 flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-slate-400 flex items-center gap-1">
              <Cpu className="w-3.5 h-3.5 text-cyan-400" /> Simulator:
            </span>
            <button
              onClick={() => setSimPaused(!simPaused)}
              className={`px-2 py-0.5 rounded text-[11px] flex items-center gap-1 border ${
                simPaused
                  ? 'bg-amber-950/60 border-amber-500/40 text-amber-300'
                  : 'bg-emerald-950/60 border-emerald-500/40 text-emerald-300'
              }`}
            >
              {simPaused ? <Play className="w-3 h-3" /> : <Pause className="w-3 h-3" />}
              <span>{simPaused ? 'SIM PAUSED' : 'SIM ACTIVE'}</span>
            </button>
          </div>

          {/* Sim Speed Selectors */}
          <div className="flex items-center gap-1 text-[11px]">
            <span className="text-slate-500">Speed:</span>
            {[1, 2, 5, 10].map((spd) => (
              <button
                key={spd}
                onClick={() => setSimSpeed(spd)}
                className={`px-1.5 py-0.5 rounded ${
                  simSpeed === spd
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
                    : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                {spd}x
              </button>
            ))}
          </div>

          {/* Sim Test Actions for Active Trade */}
          {position && (
            <div className="flex items-center gap-1.5 border-l border-white/10 pl-3">
              <span className="text-slate-500 text-[10px]">Test Injection:</span>
              <button
                onClick={handleTriggerFakePump}
                className="px-2 py-0.5 rounded bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[10px] font-semibold"
                title="Inject +15% price spike"
              >
                +15% Pump
              </button>
              <button
                onClick={handleTriggerFakeDump}
                className="px-2 py-0.5 rounded bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 text-[10px] font-semibold"
                title="Inject -12% price dump"
              >
                -12% Dump
              </button>
            </div>
          )}
        </div>

        {/* Session Stats */}
        <div className="flex items-center gap-4 text-slate-400">
          <div>
            <span>Session PnL: </span>
            <span className={`font-bold tabular-nums ${sessionPnLSOL >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {sessionPnLSOL >= 0 ? '+' : ''}{sessionPnLSOL.toFixed(3)} SOL
            </span>
          </div>
          <div className="flex items-center gap-1">
            <span>Win Rate: </span>
            <span className="text-emerald-400 font-bold">{sessionWins}W</span>
            <span>/</span>
            <span className="text-red-400 font-bold">{sessionLosses}L</span>
            <span className="text-slate-500">
              ({((sessionWins / Math.max(1, sessionWins + sessionLosses)) * 100).toFixed(0)}%)
            </span>
          </div>
        </div>
      </div>

      {/* MAIN WORKSPACE GRID */}
      <main className="flex-1 p-3 lg:p-4 space-y-4 max-w-[1680px] w-full mx-auto">
        {/* ROW 1: ACTIVE SCALP MONITOR CARD */}
        <section className="bg-[#0b0e17] border border-white/10 rounded-xl p-4 shadow-2xl relative overflow-hidden">
          {position ? (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-center">
              {/* Token Info & Identity */}
              <div className="lg:col-span-4 space-y-2">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center font-bold text-emerald-400 text-xs font-mono">
                    SOL
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="font-extrabold text-base text-white tracking-wide">
                        {position.tokenName}
                      </h2>
                      <span className="text-xs font-mono font-bold text-cyan-400 bg-cyan-950/60 border border-cyan-500/30 px-2 py-0.5 rounded">
                        {position.ticker}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
                      <span>CA:</span>
                      <span className="text-slate-300">{position.ca.slice(0, 8)}...{position.ca.slice(-6)}</span>
                      <button
                        onClick={() => copyToClipboard(position.ca, 'Contract Address')}
                        className="hover:text-emerald-400 transition-colors"
                        title="Copy Contract Address"
                      >
                        <Copy className="w-3 h-3" />
                      </button>
                      <a
                        href={`https://solscan.io/token/${position.ca}`}
                        target="_blank"
                        rel="noreferrer"
                        className="hover:text-emerald-400 transition-colors"
                        title="Solscan Explorer"
                      >
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  </div>
                </div>

                {/* Entry vs Current Real-Time Metrics & Live Sparkline */}
                <div className="grid grid-cols-2 gap-2 pt-1 font-mono text-xs">
                  <div className="bg-slate-900/80 p-2 rounded-lg border border-white/5">
                    <div className="text-slate-500 text-[10px]">Position Size</div>
                    <div className="text-slate-200 font-bold tabular-nums">
                      {position.entrySizeSOL.toFixed(4)} SOL
                    </div>
                    <div className="text-slate-500 text-[10px]">
                      ~${(position.entrySizeSOL * position.solPriceUSD).toFixed(2)}
                    </div>
                  </div>
                  <div className="bg-slate-900/80 p-2 rounded-lg border border-white/5">
                    <div className="text-slate-500 text-[10px]">Current Exit Value</div>
                    <div className="text-emerald-400 font-bold tabular-nums">
                      {currentExitValueSOL.toFixed(4)} SOL
                    </div>
                    <div className="text-slate-500 text-[10px]">
                      Net: {currentNetProfitSOL >= 0 ? '+' : ''}{currentNetProfitSOL.toFixed(4)} SOL
                    </div>
                  </div>
                </div>

                {/* Live Real-time Price Sparkline / Micro Tick Chart */}
                <div className="bg-slate-950/70 p-2 rounded-lg border border-white/5">
                  <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 mb-1">
                    <span>Live 1s Tick Progression</span>
                    <span className="text-cyan-400 font-semibold">{position.currentPriceSOL.toFixed(8)} SOL</span>
                  </div>
                  <div className="h-12 w-full flex items-end">
                    <svg className="w-full h-full overflow-visible" preserveAspectRatio="none" viewBox="0 0 100 40">
                      {/* Entry reference line */}
                      <line x1="0" y1="20" x2="100" y2="20" stroke="rgba(255,255,255,0.2)" strokeDasharray="2,2" strokeWidth="0.8" />
                      {/* Polyline of price */}
                      {position.priceHistory.length > 1 && (
                        <polyline
                          fill="none"
                          stroke={currentPnLPct >= 0 ? '#10b981' : '#ef4444'}
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          points={position.priceHistory
                            .map((pt, idx) => {
                              const x = (idx / (position.priceHistory.length - 1)) * 100;
                              // normalize y around entry price
                              const y = 20 - (pt.pnl / 25) * 16;
                              return `${x},${Math.max(2, Math.min(38, y))}`;
                            })
                            .join(' ')}
                        />
                      )}
                    </svg>
                  </div>
                </div>
              </div>

              {/* Center PnL Glow Badge & Strategy Execution Telemetry */}
              <div className="lg:col-span-5 flex flex-col items-center justify-center p-3 bg-slate-900/50 rounded-xl border border-white/5 space-y-3">
                {/* Large Glowing Realized PnL badge */}
                <div className="flex items-baseline gap-3">
                  <div
                    className={`text-3xl lg:text-4xl font-black font-mono tracking-tight tabular-nums px-4 py-1.5 rounded-xl border ${
                      currentPnLPct >= 0
                        ? 'text-emerald-400 border-emerald-500/40 bg-emerald-950/40 glow-emerald'
                        : 'text-red-400 border-red-500/40 bg-red-950/40 glow-crimson'
                    }`}
                  >
                    {currentPnLPct >= 0 ? '+' : ''}{currentPnLPct.toFixed(2)}%
                  </div>
                  <div className="text-xs font-mono text-slate-400">
                    <div>High: <span className="text-slate-200 font-semibold">{((position.highestPriceSOL - position.entryPriceSOL) / position.entryPriceSOL * 100).toFixed(1)}%</span></div>
                    <div>Stop: <span className="text-red-400 font-semibold">{settings.stopLossPct.toFixed(1)}%</span></div>
                  </div>
                </div>

                {/* Strategy Execution State Badges */}
                <div className="flex flex-wrap items-center justify-center gap-2 text-[11px] font-mono w-full">
                  {/* Breakeven Floor */}
                  <div
                    className={`flex items-center gap-1 px-2 py-1 rounded border transition-colors ${
                      position.breakevenTriggered
                        ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300 font-semibold'
                        : 'bg-slate-950 border-white/10 text-slate-500'
                    }`}
                  >
                    <ShieldCheck className="w-3 h-3 text-emerald-400" />
                    <span>Breakeven: {position.breakevenTriggered ? 'LOCKED (+0.5%)' : 'Armed (+5%)'}</span>
                  </div>

                  {/* Trailing Stop */}
                  <div
                    className={`flex items-center gap-1 px-2 py-1 rounded border transition-colors ${
                      position.trailingStopActive
                        ? 'bg-purple-500/10 border-purple-500/40 text-purple-300 font-semibold'
                        : 'bg-slate-950 border-white/10 text-slate-500'
                    }`}
                  >
                    <TrendingUp className="w-3 h-3 text-purple-400" />
                    <span>Trailing Stop: {position.trailingStopActive ? 'TRIGGERED (3.5% drop)' : 'Armed (+8%)'}</span>
                  </div>

                  {/* Hard TP & SL */}
                  <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-slate-950 border border-white/10 text-slate-400">
                    <span className="text-emerald-400 font-semibold">TP: +{settings.takeProfitPct}%</span>
                    <span>·</span>
                    <span className="text-red-400 font-semibold">SL: {settings.stopLossPct}%</span>
                  </div>
                </div>

                {/* Stagnation Countdown Bar */}
                <div className="w-full space-y-1">
                  <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
                    <span className="flex items-center gap-1">
                      <Timer className="w-3 h-3 text-amber-400" /> Stagnation Timeout:
                    </span>
                    <span className="text-amber-300 font-semibold tabular-nums">
                      {position.stagnationSeconds}s / {position.maxStagnationSeconds}s
                    </span>
                  </div>
                  <div className="w-full h-1.5 bg-slate-950 rounded-full overflow-hidden border border-white/5">
                    <div
                      className={`h-full transition-all duration-300 ${
                        stagnationPercent > 75
                          ? 'bg-red-500'
                          : stagnationPercent > 50
                          ? 'bg-amber-400'
                          : 'bg-cyan-500'
                      }`}
                      style={{ width: `${stagnationPercent}%` }}
                    />
                  </div>
                </div>
              </div>

              {/* Panic Sell & Fast Exit Action */}
              <div className="lg:col-span-3 flex flex-col justify-center gap-2">
                <button
                  onClick={handlePanicSell}
                  className="w-full py-3.5 px-4 rounded-xl bg-gradient-to-r from-red-600 via-rose-600 to-red-700 hover:from-red-500 hover:to-rose-600 text-white font-black text-sm tracking-wider uppercase shadow-xl glow-crimson flex items-center justify-center gap-2 transition-transform active:scale-95 border border-red-400/40 cursor-pointer animate-pulse"
                >
                  <AlertTriangle className="w-5 h-5 text-white" />
                  <span>EMERGENCY MARKET SELL (100%)</span>
                </button>
                <div className="text-[10px] font-mono text-center text-slate-500">
                  Instant Jito MEV priority broadcast · 5% slippage protection
                </div>
              </div>
            </div>
          ) : (
            <div className="py-6 flex flex-col items-center justify-center text-center space-y-3">
              <div className="w-12 h-12 rounded-full bg-slate-900 border border-white/10 flex items-center justify-center text-slate-500">
                <Activity className="w-6 h-6 text-emerald-400" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-200">No Active Scalp Trade</h3>
                <p className="text-xs text-slate-400 max-w-md mt-0.5">
                  Sniper is scanning PumpPortal WebSocket and DexScreener momentum pools.
                  When a token meets your strategy thresholds, it will auto-snipe or you can manual scalp below.
                </p>
              </div>
              <div className="flex items-center gap-2 pt-1">
                <button
                  onClick={() => {
                    if (discoveredTokens.length > 0) {
                      handleManualScalp(discoveredTokens[0]);
                    }
                  }}
                  className="px-4 py-2 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs rounded-lg shadow-lg flex items-center gap-2 transition-all cursor-pointer"
                >
                  <Zap className="w-4 h-4" />
                  <span>Quick Scalp Top Pick ({discoveredTokens[0]?.ticker || '$GIGAQUANT'})</span>
                </button>
              </div>
            </div>
          )}
        </section>

        {/* ROW 2: DUAL INDEPENDENT LOG STREAMS (SPLIT VIEW) */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* LEFT STREAM: DEXSCREENER MOMENTUM SCANNER */}
          <div className="bg-[#0b0e17] border border-cyan-500/20 rounded-xl flex flex-col h-[460px] shadow-xl overflow-hidden">
            {/* Terminal Header */}
            <div className="bg-[#0e1320] border-b border-cyan-500/20 px-3 py-2 flex items-center justify-between text-xs font-mono">
              <div className="flex items-center gap-2">
                <Radio className="w-4 h-4 text-cyan-400 animate-pulse" />
                <span className="font-bold text-cyan-300 tracking-wider">
                  DEXSCREENER MOMENTUM SCANNER
                </span>
                <span className="text-[10px] text-slate-400 bg-cyan-950/80 border border-cyan-500/30 px-1.5 py-0.2 rounded">
                  {filteredDexLogs.length} events
                </span>
              </div>

              {/* Stream Actions */}
              <div className="flex items-center gap-1.5">
                {/* Auto Scroll Toggle */}
                <button
                  onClick={() => setDexAutoScroll(!dexAutoScroll)}
                  className={`px-2 py-0.5 rounded text-[10px] font-semibold border transition-colors ${
                    dexAutoScroll
                      ? 'bg-cyan-500/20 border-cyan-500/40 text-cyan-300'
                      : 'bg-slate-900 border-white/10 text-slate-500'
                  }`}
                  title="Toggle Sticky Auto-Scroll"
                >
                  {dexAutoScroll ? 'SCROLL: ON' : 'SCROLL: PAUSED'}
                </button>
                <button
                  onClick={() => {
                    const allText = dexLogs.map((l) => `[${l.timestamp}] [${l.tag}] ${l.message}`).join('\n');
                    copyToClipboard(allText, 'DexScreener Logs');
                  }}
                  className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300"
                  title="Copy All Dex Logs"
                >
                  <Copy className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setDexLogs([])}
                  className="p-1 rounded bg-slate-800 hover:bg-red-950 hover:text-red-400 text-slate-400"
                  title="Clear Dex Logs"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* Filter & Search Bar */}
            <div className="bg-[#090c13] px-3 py-1.5 border-b border-white/5 flex items-center justify-between gap-2 text-xs font-mono">
              <div className="relative flex-1">
                <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2 top-2" />
                <input
                  type="text"
                  placeholder="Filter ticker, CA, or text..."
                  value={dexFilter}
                  onChange={(e) => setDexFilter(e.target.value)}
                  className="w-full bg-slate-950 border border-white/10 rounded pl-7 pr-2 py-1 text-slate-200 placeholder-slate-600 text-xs focus:outline-none focus:border-cyan-500/50"
                />
              </div>
              {/* Level Segment */}
              <div className="flex items-center gap-1 text-[10px]">
                {['ALL', 'APPROVED', 'WARNING', 'INFO'].map((lvl) => (
                  <button
                    key={lvl}
                    onClick={() => setDexLevelFilter(lvl)}
                    className={`px-1.5 py-0.5 rounded ${
                      dexLevelFilter === lvl
                        ? 'bg-cyan-500/30 text-cyan-200 font-bold border border-cyan-500/40'
                        : 'text-slate-500 hover:text-slate-300'
                    }`}
                  >
                    {lvl}
                  </button>
                ))}
              </div>
            </div>

            {/* Log Stream Content */}
            <div
              ref={dexScrollRef}
              className="flex-1 overflow-y-auto p-2.5 font-mono text-[11px] space-y-1.5 bg-[#080b12]"
            >
              {filteredDexLogs.length === 0 ? (
                <div className="h-full flex items-center justify-center text-slate-600 italic">
                  No matching DexScreener logs found...
                </div>
              ) : (
                filteredDexLogs.map((log) => (
                  <div
                    key={log.id}
                    className={`p-1.5 rounded border transition-colors leading-relaxed ${
                      log.level === 'approved'
                        ? 'bg-emerald-950/30 border-emerald-500/30 text-emerald-300'
                        : log.level === 'danger'
                        ? 'bg-red-950/30 border-red-500/30 text-red-300'
                        : log.level === 'warning'
                        ? 'bg-amber-950/30 border-amber-500/30 text-amber-300'
                        : 'bg-slate-900/40 border-white/5 text-slate-300'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-slate-500 select-none text-[10px]">[{log.timestamp}]</span>
                      <span
                        className={`text-[9px] uppercase px-1 py-0.2 rounded font-bold ${
                          log.level === 'approved'
                            ? 'bg-emerald-500 text-slate-950'
                            : log.level === 'danger'
                            ? 'bg-red-500 text-white'
                            : log.level === 'warning'
                            ? 'bg-amber-500 text-slate-950'
                            : 'bg-cyan-900/60 text-cyan-300 border border-cyan-500/30'
                        }`}
                      >
                        {log.tag}
                      </span>
                      {log.ticker && (
                        <span className="text-cyan-400 font-bold bg-cyan-950/50 px-1 rounded text-[10px]">
                          {log.ticker}
                        </span>
                      )}
                    </div>
                    <div className="mt-0.5 text-slate-200">{log.message}</div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* RIGHT STREAM: PUMP.FUN WEBSOCKET SNIPER */}
          <div className="bg-[#0b0e17] border border-amber-500/20 rounded-xl flex flex-col h-[460px] shadow-xl overflow-hidden">
            {/* Terminal Header */}
            <div className="bg-[#18120c] border-b border-amber-500/20 px-3 py-2 flex items-center justify-between text-xs font-mono">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-400 animate-pulse" />
                <span className="font-bold text-amber-300 tracking-wider">
                  PUMP.FUN WEBSOCKET SNIPER
                </span>
                <span className="text-[10px] text-slate-400 bg-amber-950/80 border border-amber-500/30 px-1.5 py-0.2 rounded">
                  {filteredPumpLogs.length} events
                </span>
              </div>

              {/* Stream Actions */}
              <div className="flex items-center gap-1.5">
                {/* Auto Scroll Toggle */}
                <button
                  onClick={() => setPumpAutoScroll(!pumpAutoScroll)}
                  className={`px-2 py-0.5 rounded text-[10px] font-semibold border transition-colors ${
                    pumpAutoScroll
                      ? 'bg-amber-500/20 border-amber-500/40 text-amber-300'
                      : 'bg-slate-900 border-white/10 text-slate-500'
                  }`}
                  title="Toggle Sticky Auto-Scroll"
                >
                  {pumpAutoScroll ? 'SCROLL: ON' : 'SCROLL: PAUSED'}
                </button>
                <button
                  onClick={() => {
                    const allText = pumpLogs.map((l) => `[${l.timestamp}] [${l.tag}] ${l.message}`).join('\n');
                    copyToClipboard(allText, 'Pump.fun Logs');
                  }}
                  className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300"
                  title="Copy All Pump Logs"
                >
                  <Copy className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setPumpLogs([])}
                  className="p-1 rounded bg-slate-800 hover:bg-red-950 hover:text-red-400 text-slate-400"
                  title="Clear Pump Logs"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* Filter & Search Bar */}
            <div className="bg-[#090c13] px-3 py-1.5 border-b border-white/5 flex items-center justify-between gap-2 text-xs font-mono">
              <div className="relative flex-1">
                <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2 top-2" />
                <input
                  type="text"
                  placeholder="Filter ticker, CA, or text..."
                  value={pumpFilter}
                  onChange={(e) => setPumpFilter(e.target.value)}
                  className="w-full bg-slate-950 border border-white/10 rounded pl-7 pr-2 py-1 text-slate-200 placeholder-slate-600 text-xs focus:outline-none focus:border-amber-500/50"
                />
              </div>
              {/* Level Segment */}
              <div className="flex items-center gap-1 text-[10px]">
                {['ALL', 'APPROVED', 'DANGER', 'INFO'].map((lvl) => (
                  <button
                    key={lvl}
                    onClick={() => setPumpLevelFilter(lvl)}
                    className={`px-1.5 py-0.5 rounded ${
                      pumpLevelFilter === lvl
                        ? 'bg-amber-500/30 text-amber-200 font-bold border border-amber-500/40'
                        : 'text-slate-500 hover:text-slate-300'
                    }`}
                  >
                    {lvl}
                  </button>
                ))}
              </div>
            </div>

            {/* Log Stream Content */}
            <div
              ref={pumpScrollRef}
              className="flex-1 overflow-y-auto p-2.5 font-mono text-[11px] space-y-1.5 bg-[#0a0c10]"
            >
              {filteredPumpLogs.length === 0 ? (
                <div className="h-full flex items-center justify-center text-slate-600 italic">
                  No matching Pump.fun logs found...
                </div>
              ) : (
                filteredPumpLogs.map((log) => (
                  <div
                    key={log.id}
                    className={`p-1.5 rounded border transition-colors leading-relaxed ${
                      log.level === 'approved'
                        ? 'bg-emerald-950/30 border-emerald-500/30 text-emerald-300'
                        : log.level === 'danger'
                        ? 'bg-red-950/30 border-red-500/30 text-red-300'
                        : log.level === 'warning'
                        ? 'bg-amber-950/30 border-amber-500/30 text-amber-300'
                        : 'bg-slate-900/40 border-white/5 text-slate-300'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-slate-500 select-none text-[10px]">[{log.timestamp}]</span>
                      <span
                        className={`text-[9px] uppercase px-1 py-0.2 rounded font-bold ${
                          log.level === 'approved'
                            ? 'bg-emerald-500 text-slate-950'
                            : log.level === 'danger'
                            ? 'bg-red-500 text-white'
                            : log.level === 'warning'
                            ? 'bg-amber-500 text-slate-950'
                            : 'bg-amber-900/60 text-amber-300 border border-amber-500/30'
                        }`}
                      >
                        {log.tag}
                      </span>
                      {log.ticker && (
                        <span className="text-amber-400 font-bold bg-amber-950/50 px-1 rounded text-[10px]">
                          {log.ticker}
                        </span>
                      )}
                    </div>
                    <div className="mt-0.5 text-slate-200">{log.message}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        </section>

        {/* ROW 3: DISCOVERED OPPORTUNITIES FEED (CARDS GRID) */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-emerald-400" />
              <h2 className="text-sm font-extrabold text-white tracking-wider font-mono uppercase">
                QUALIFIED SCALP OPPORTUNITIES
              </h2>
              <span className="text-xs text-slate-400 font-mono">
                (Met RugCheck, OSINT social filters &amp; momentum triggers)
              </span>
            </div>
            <div className="text-xs text-slate-400 font-mono">
              Auto-Evaluating 24/7 via Helius RPC
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {discoveredTokens.map((token) => (
              <div
                key={token.id}
                className="bg-[#0b0e17] border border-white/10 hover:border-emerald-500/40 rounded-xl p-3.5 space-y-3 transition-all hover:shadow-xl hover:shadow-emerald-500/5 group flex flex-col justify-between"
              >
                {/* Header */}
                <div>
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="font-extrabold text-white text-sm tracking-wide">
                          {token.ticker}
                        </span>
                        <span className="text-[10px] text-slate-400">· {token.discoveredAt}</span>
                      </div>
                      <div className="text-xs text-slate-400 truncate max-w-[170px]">
                        {token.name}
                      </div>
                    </div>
                    <button
                      onClick={() => handleManualScalp(token)}
                      className="px-2.5 py-1 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs rounded-lg transition-transform active:scale-95 flex items-center gap-1 cursor-pointer"
                    >
                      <Zap className="w-3 h-3" />
                      <span>Scalp</span>
                    </button>
                  </div>

                  {/* Financial & Pool Depth Metrics */}
                  <div className="grid grid-cols-3 gap-1.5 bg-slate-900/60 p-2 rounded-lg border border-white/5 font-mono text-[11px] mt-2.5">
                    <div>
                      <div className="text-slate-500 text-[9px]">MCap</div>
                      <div className="text-slate-200 font-semibold tabular-nums">
                        ${(token.marketCapUSD / 1000).toFixed(1)}K
                      </div>
                    </div>
                    <div>
                      <div className="text-slate-500 text-[9px]">5m Vol</div>
                      <div className="text-cyan-400 font-semibold tabular-nums">
                        ${(token.vol5mUSD / 1000).toFixed(1)}K
                      </div>
                    </div>
                    <div>
                      <div className="text-slate-500 text-[9px]">Liquidity</div>
                      <div className="text-slate-200 font-semibold tabular-nums">
                        ${(token.liquidityUSD / 1000).toFixed(1)}K
                      </div>
                    </div>
                  </div>

                  {/* Bonding Curve Progress */}
                  <div className="space-y-1 mt-2 font-mono text-[10px]">
                    <div className="flex items-center justify-between text-slate-400">
                      <span>Bonding Curve:</span>
                      <span className="text-emerald-400 font-bold">{token.bondingCurveProgress}%</span>
                    </div>
                    <div className="w-full h-1 bg-slate-950 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-emerald-500 to-cyan-400"
                        style={{ width: `${token.bondingCurveProgress}%` }}
                      />
                    </div>
                  </div>

                  {/* Safety & OSINT Badges */}
                  <div className="flex flex-wrap items-center gap-1.5 pt-2 text-[10px] font-mono">
                    <span className="bg-emerald-950/60 border border-emerald-500/30 text-emerald-400 px-1.5 py-0.5 rounded flex items-center gap-1">
                      <ShieldCheck className="w-3 h-3" />
                      RugCheck: {token.rugcheckScore}/500 Safe
                    </span>
                    <span className="bg-slate-900 border border-white/10 text-slate-300 px-1.5 py-0.5 rounded">
                      Top 10: {token.top10Concentration}%
                    </span>
                  </div>
                </div>

                {/* Social Badges & Links */}
                <div className="pt-2 border-t border-white/5 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    {token.twitter && (
                      <a
                        href={token.twitter}
                        target="_blank"
                        rel="noreferrer"
                        className="text-slate-400 hover:text-cyan-400 transition-colors p-1"
                        title="Twitter / X"
                      >
                        <Twitter className="w-3.5 h-3.5" />
                      </a>
                    )}
                    {token.telegram && (
                      <a
                        href={token.telegram}
                        target="_blank"
                        rel="noreferrer"
                        className="text-slate-400 hover:text-cyan-400 transition-colors p-1"
                        title="Telegram Community"
                      >
                        <Send className="w-3.5 h-3.5" />
                      </a>
                    )}
                    {token.website && (
                      <a
                        href={token.website}
                        target="_blank"
                        rel="noreferrer"
                        className="text-slate-400 hover:text-cyan-400 transition-colors p-1"
                        title="Website"
                      >
                        <Globe className="w-3.5 h-3.5" />
                      </a>
                    )}
                  </div>
                  <button
                    onClick={() => copyToClipboard(token.ca, 'Contract Address')}
                    className="text-[10px] font-mono text-slate-500 hover:text-slate-300 flex items-center gap-1"
                  >
                    <Copy className="w-3 h-3" />
                    <span>Copy CA</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ROW 4: EXECUTED TRADES (CLOSED SCALP HISTORY) */}
        <section className="bg-[#0b0e17] border border-white/10 rounded-xl p-4 shadow-xl space-y-4 overflow-hidden">
          {/* Section Header */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 pb-3">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center">
                <History className="w-4 h-4 text-emerald-400" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-extrabold text-white tracking-wider font-mono uppercase">
                    EXECUTED TRADES (CLOSED SCALP HISTORY)
                  </h2>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 border border-white/10 text-cyan-400 font-bold">
                    {executedTrades.length} Closed
                  </span>
                </div>
                <p className="text-xs text-slate-400 font-mono">
                  Real-time ledger of completed scalps, triggers, holding durations &amp; realized SOL returns
                </p>
              </div>
            </div>

            {/* Header Summary & Actions */}
            <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
              {/* Total Realized PnL Pill */}
              <div
                className={`px-3 py-1.5 rounded-lg border flex items-center gap-1.5 font-bold tabular-nums ${
                  totalExecutedPnlSOL >= 0
                    ? 'bg-emerald-950/60 border-emerald-500/40 text-emerald-300'
                    : 'bg-red-950/60 border-red-500/40 text-red-300'
                }`}
              >
                <span>Realized:</span>
                <span>
                  {totalExecutedPnlSOL >= 0 ? '+' : ''}
                  {totalExecutedPnlSOL.toFixed(4)} SOL
                </span>
                <span className="text-[10px] text-slate-400">
                  (~${(totalExecutedPnlSOL * 175.4).toFixed(2)})
                </span>
              </div>

              {/* Export CSV Button */}
              <button
                onClick={exportTradesCSV}
                className="px-2.5 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-white/10 flex items-center gap-1.5 transition-colors cursor-pointer"
                title="Export Trades to CSV"
              >
                <Download className="w-3.5 h-3.5 text-cyan-400" />
                <span>Export CSV</span>
              </button>

              {/* Clear History / Restore Sample Buttons */}
              {executedTrades.length > 0 ? (
                <button
                  onClick={clearExecutedTrades}
                  className="px-2 py-1.5 rounded-lg bg-slate-900 hover:bg-red-950/60 text-slate-400 hover:text-red-300 border border-white/10 transition-colors cursor-pointer"
                  title="Clear Trade History"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              ) : (
                <button
                  onClick={restoreSampleTrades}
                  className="px-2.5 py-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 text-xs font-semibold cursor-pointer"
                >
                  Restore Sample Trades
                </button>
              )}
            </div>
          </div>

          {/* Quick Metrics Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
            <div className="bg-slate-950/80 p-2.5 rounded-lg border border-white/5 space-y-0.5">
              <div className="text-[10px] text-slate-500 uppercase flex items-center gap-1">
                <BarChart3 className="w-3 h-3 text-cyan-400" /> Win Rate
              </div>
              <div className="text-sm font-bold text-slate-100 tabular-nums">
                {executedTrades.length > 0
                  ? ((totalExecutedWins / executedTrades.length) * 100).toFixed(1)
                  : '0'}
                %
              </div>
              <div className="text-[10px] text-slate-400">
                <span className="text-emerald-400 font-semibold">{totalExecutedWins}W</span> ·{' '}
                <span className="text-red-400 font-semibold">{totalExecutedLosses}L</span>
              </div>
            </div>

            <div className="bg-slate-950/80 p-2.5 rounded-lg border border-white/5 space-y-0.5">
              <div className="text-[10px] text-slate-500 uppercase flex items-center gap-1">
                <Clock className="w-3 h-3 text-amber-400" /> Avg Hold Duration
              </div>
              <div className="text-sm font-bold text-amber-300 tabular-nums">
                {formatDuration(avgTradeDurationSec)}
              </div>
              <div className="text-[10px] text-slate-400">Sub-minute scalp average</div>
            </div>

            <div className="bg-slate-950/80 p-2.5 rounded-lg border border-white/5 space-y-0.5">
              <div className="text-[10px] text-slate-500 uppercase flex items-center gap-1">
                <Coins className="w-3 h-3 text-purple-400" /> Total Scalped Vol
              </div>
              <div className="text-sm font-bold text-slate-100 tabular-nums">
                {(executedTrades.reduce((acc, t) => acc + t.entrySizeSOL, 0)).toFixed(3)} SOL
              </div>
              <div className="text-[10px] text-slate-400">Across {executedTrades.length} trades</div>
            </div>

            <div className="bg-slate-950/80 p-2.5 rounded-lg border border-white/5 space-y-0.5">
              <div className="text-[10px] text-slate-500 uppercase flex items-center gap-1">
                <TrendingUp className="w-3 h-3 text-emerald-400" /> Best Winning Scalp
              </div>
              <div className="text-sm font-bold text-emerald-400 tabular-nums">
                {executedTrades.length > 0
                  ? `+${Math.max(0, ...executedTrades.map((t) => t.pnlPct)).toFixed(1)}%`
                  : '0%'}
              </div>
              <div className="text-[10px] text-slate-400">Hard TP hit ceiling</div>
            </div>
          </div>

          {/* Filter & Search Bar */}
          <div className="bg-[#090c13] p-2 rounded-lg border border-white/5 flex flex-wrap items-center justify-between gap-2 text-xs font-mono">
            {/* Search Input */}
            <div className="relative flex-1 min-w-[200px]">
              <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2.5" />
              <input
                type="text"
                placeholder="Search symbol, name, or contract address..."
                value={tradesSearch}
                onChange={(e) => setTradesSearch(e.target.value)}
                className="w-full bg-slate-950 border border-white/10 rounded-lg pl-8 pr-3 py-1.5 text-slate-200 placeholder-slate-600 text-xs focus:outline-none focus:border-cyan-500/50"
              />
            </div>

            {/* Outcome Segment Filters */}
            <div className="flex flex-wrap items-center gap-1 text-[11px]">
              <span className="text-slate-500 text-[10px] mr-1 flex items-center gap-1">
                <Filter className="w-3 h-3" /> Filter:
              </span>
              {[
                { id: 'ALL', label: 'ALL' },
                { id: 'WINS', label: 'WINS 🟢' },
                { id: 'LOSSES', label: 'LOSSES 🔴' },
                { id: 'TP', label: 'TAKE PROFIT' },
                { id: 'SL', label: 'STOP LOSS' },
                { id: 'PANIC', label: 'PANIC' }
              ].map((filterTab) => (
                <button
                  key={filterTab.id}
                  onClick={() => setTradesOutcomeFilter(filterTab.id as typeof tradesOutcomeFilter)}
                  className={`px-2 py-1 rounded-md transition-colors ${
                    tradesOutcomeFilter === filterTab.id
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
                      : 'text-slate-400 hover:text-white bg-slate-900 border border-white/5'
                  }`}
                >
                  {filterTab.label}
                </button>
              ))}
            </div>
          </div>

          {/* Executed Trades Table */}
          <div className="overflow-x-auto rounded-lg border border-white/10 bg-[#080b12]">
            {filteredExecutedTrades.length === 0 ? (
              <div className="py-12 flex flex-col items-center justify-center text-center space-y-2">
                <History className="w-8 h-8 text-slate-600" />
                <div className="text-slate-300 font-semibold text-xs font-mono">
                  No executed trades found matching current criteria
                </div>
                <p className="text-slate-500 text-[11px] font-mono max-w-sm">
                  Trades will automatically record here upon reaching Take Profit, Trailing Stop, Stop Loss, or Panic Sell.
                </p>
                {executedTrades.length === 0 && (
                  <button
                    onClick={restoreSampleTrades}
                    className="mt-2 px-3 py-1 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 rounded-lg text-xs font-mono font-semibold"
                  >
                    Restore Demo Trades
                  </button>
                )}
              </div>
            ) : (
              <table className="w-full text-left font-mono text-xs">
                <thead>
                  <tr className="border-b border-white/10 bg-slate-900/60 text-slate-400 text-[11px] select-none">
                    <th className="py-2.5 px-3">Symbol &amp; Token</th>
                    <th className="py-2.5 px-3">Exit Trigger</th>
                    <th className="py-2.5 px-3 text-right">Entry Price</th>
                    <th className="py-2.5 px-3 text-right">Exit Price</th>
                    <th className="py-2.5 px-3 text-right">Position Size</th>
                    <th className="py-2.5 px-3 text-center">Duration</th>
                    <th className="py-2.5 px-3 text-right">Profit / Loss</th>
                    <th className="py-2.5 px-3 text-right">Time &amp; Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {filteredExecutedTrades.map((trade) => {
                    const isWin = trade.pnlSOL > 0;
                    const triggerInfo = getExitTypeInfo(trade.exitType);

                    return (
                      <tr
                        key={trade.id}
                        className="hover:bg-slate-900/40 transition-colors group"
                      >
                        {/* Symbol & Name */}
                        <td className="py-3 px-3">
                          <div className="flex items-center gap-2">
                            <span className="font-extrabold text-white text-xs px-2 py-0.5 rounded bg-slate-900 border border-white/10 group-hover:border-cyan-500/40 transition-colors">
                              {trade.symbol}
                            </span>
                            <div>
                              <div className="text-slate-300 text-xs font-semibold truncate max-w-[130px]">
                                {trade.tokenName}
                              </div>
                              <div className="flex items-center gap-1.5 text-[10px] text-slate-500">
                                <span>CA: {trade.ca.slice(0, 4)}...{trade.ca.slice(-4)}</span>
                                <button
                                  onClick={() => copyToClipboard(trade.ca, 'Contract Address')}
                                  className="hover:text-cyan-400 transition-colors"
                                  title="Copy Contract Address"
                                >
                                  <Copy className="w-2.5 h-2.5" />
                                </button>
                                <a
                                  href={`https://solscan.io/token/${trade.ca}`}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="hover:text-emerald-400 transition-colors"
                                  title="View on Solscan"
                                >
                                  <ExternalLink className="w-2.5 h-2.5" />
                                </a>
                              </div>
                            </div>
                          </div>
                        </td>

                        {/* Exit Trigger */}
                        <td className="py-3 px-3">
                          <div
                            className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-[10px] font-semibold ${triggerInfo.badgeClass}`}
                          >
                            <span className={`w-1.5 h-1.5 rounded-full ${triggerInfo.dotClass}`} />
                            <span>{triggerInfo.label}</span>
                          </div>
                        </td>

                        {/* Entry Price */}
                        <td className="py-3 px-3 text-right tabular-nums text-slate-300">
                          {trade.entryPriceSOL.toFixed(8)}
                          <span className="text-[10px] text-slate-500 ml-1">SOL</span>
                        </td>

                        {/* Exit Price */}
                        <td className="py-3 px-3 text-right tabular-nums text-slate-200 font-semibold">
                          {trade.exitPriceSOL.toFixed(8)}
                          <span className="text-[10px] text-slate-500 ml-1">SOL</span>
                        </td>

                        {/* Position Size */}
                        <td className="py-3 px-3 text-right tabular-nums text-slate-300">
                          <div>{trade.entrySizeSOL.toFixed(4)} SOL</div>
                          <div className="text-[10px] text-slate-500">
                            Exit: {trade.exitValueSOL.toFixed(4)} SOL
                          </div>
                        </td>

                        {/* Duration */}
                        <td className="py-3 px-3 text-center">
                          <span className="inline-flex items-center gap-1 text-slate-300 bg-slate-900/80 px-2 py-0.5 rounded border border-white/5 text-[11px] tabular-nums">
                            <Clock className="w-3 h-3 text-amber-400" />
                            <span>{formatDuration(trade.durationSeconds)}</span>
                          </span>
                        </td>

                        {/* Profit / Loss */}
                        <td className="py-3 px-3 text-right">
                          <div
                            className={`inline-block px-2.5 py-1 rounded-lg border font-bold tabular-nums ${
                              isWin
                                ? 'bg-emerald-950/60 border-emerald-500/40 text-emerald-300 glow-emerald'
                                : 'bg-red-950/60 border-red-500/40 text-red-300 glow-crimson'
                            }`}
                          >
                            <div className="flex items-center justify-end gap-1">
                              {isWin ? (
                                <TrendingUp className="w-3 h-3 text-emerald-400" />
                              ) : (
                                <TrendingDown className="w-3 h-3 text-red-400" />
                              )}
                              <span>
                                {isWin ? '+' : ''}
                                {trade.pnlPct.toFixed(2)}%
                              </span>
                            </div>
                            <div className="text-[10px] opacity-90 text-right">
                              {isWin ? '+' : ''}
                              {trade.pnlSOL.toFixed(5)} SOL
                            </div>
                          </div>
                        </td>

                        {/* Timestamp & Actions */}
                        <td className="py-3 px-3 text-right">
                          <div className="text-slate-400 text-[11px] tabular-nums">
                            {trade.timestamp}
                          </div>
                          <button
                            onClick={() => {
                              const matchTok = discoveredTokens.find((d) => d.ticker === trade.symbol);
                              if (matchTok) {
                                handleManualScalp(matchTok);
                              } else {
                                handleManualScalp({
                                  id: 're_' + Date.now(),
                                  ticker: trade.symbol,
                                  name: trade.tokenName,
                                  ca: trade.ca,
                                  marketCapUSD: 45000,
                                  vol5mUSD: 50000,
                                  liquidityUSD: 18000,
                                  bondingCurveProgress: 45,
                                  rugcheckScore: 0,
                                  top10Concentration: 12,
                                  devBoughtSOL: 2,
                                  discoveredAt: 'Recent'
                                });
                              }
                            }}
                            className="mt-1 px-2 py-0.5 rounded bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[10px] font-semibold inline-flex items-center gap-1 transition-colors cursor-pointer"
                            title="Re-enter scalp on this token"
                          >
                            <Zap className="w-2.5 h-2.5" />
                            <span>Re-Scalp</span>
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </section>
      </main>

      {/* BOT STRATEGY SETTINGS DRAWER / MODAL */}
      {isSettingsOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0e121b] border border-white/20 rounded-2xl max-w-xl w-full p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <div className="flex items-center gap-2">
                <Sliders className="w-5 h-5 text-cyan-400" />
                <h3 className="font-extrabold text-base text-white tracking-wide font-mono">
                  BOT STRATEGY &amp; RISK ENGINE CONFIG
                </h3>
              </div>
              <button
                onClick={() => setIsSettingsOpen(false)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-2 text-xs font-mono">
              {/* Order Sizing & Priority Tip */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-slate-400">Trade Size (SOL)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.005"
                    value={settings.tradeSizeSOL}
                    onChange={(e) => setSettings({ ...settings, tradeSizeSOL: parseFloat(e.target.value) || 0.02 })}
                    className="w-full bg-slate-900 border border-white/10 rounded-lg px-3 py-2 text-slate-100 font-bold focus:border-cyan-400"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-slate-400">Jito MEV Tip (SOL)</label>
                  <input
                    type="number"
                    step="0.001"
                    min="0.0005"
                    value={settings.jitoTipSOL}
                    onChange={(e) => setSettings({ ...settings, jitoTipSOL: parseFloat(e.target.value) || 0.002 })}
                    className="w-full bg-slate-900 border border-white/10 rounded-lg px-3 py-2 text-slate-100 font-bold focus:border-cyan-400"
                  />
                </div>
              </div>

              {/* Slippage & Take Profit */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-slate-400">Slippage Tolerance (bps)</label>
                  <input
                    type="number"
                    step="50"
                    value={settings.slippageBps}
                    onChange={(e) => setSettings({ ...settings, slippageBps: parseInt(e.target.value) || 500 })}
                    className="w-full bg-slate-900 border border-white/10 rounded-lg px-3 py-2 text-slate-100 font-bold focus:border-cyan-400"
                  />
                  <div className="text-[10px] text-slate-500">500 bps = 5.0%</div>
                </div>
                <div className="space-y-1">
                  <label className="text-slate-400">Hard Take Profit (%)</label>
                  <input
                    type="number"
                    step="1"
                    value={settings.takeProfitPct}
                    onChange={(e) => setSettings({ ...settings, takeProfitPct: parseFloat(e.target.value) || 25 })}
                    className="w-full bg-slate-900 border border-white/10 rounded-lg px-3 py-2 text-emerald-400 font-bold focus:border-emerald-400"
                  />
                </div>
              </div>

              {/* Stop Loss & Stagnation */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-slate-400">Hard Stop Loss (%)</label>
                  <input
                    type="number"
                    step="1"
                    value={settings.stopLossPct}
                    onChange={(e) => setSettings({ ...settings, stopLossPct: parseFloat(e.target.value) || -10 })}
                    className="w-full bg-slate-900 border border-white/10 rounded-lg px-3 py-2 text-red-400 font-bold focus:border-red-400"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-slate-400">Stagnation Timeout (Sec)</label>
                  <input
                    type="number"
                    step="10"
                    value={settings.stagnationLimitSec}
                    onChange={(e) => setSettings({ ...settings, stagnationLimitSec: parseInt(e.target.value) || 240 })}
                    className="w-full bg-slate-900 border border-white/10 rounded-lg px-3 py-2 text-amber-400 font-bold focus:border-amber-400"
                  />
                </div>
              </div>

              {/* Breakeven & Trailing Stop Thresholds */}
              <div className="p-3 bg-slate-900/60 rounded-xl border border-white/5 space-y-2">
                <div className="font-bold text-slate-200">Trailing Stop &amp; Breakeven Engine</div>
                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  <div>
                    <span className="text-slate-400">Breakeven Trigger:</span> +{settings.breakevenTriggerPct}%
                  </div>
                  <div>
                    <span className="text-slate-400">Locked Floor:</span> +{settings.breakevenFloorPct}%
                  </div>
                  <div>
                    <span className="text-slate-400">Trailing Trigger:</span> +{settings.trailingStopTriggerPct}%
                  </div>
                  <div>
                    <span className="text-slate-400">Trailing Pullback:</span> {settings.trailingStopDropPct}%
                  </div>
                </div>
              </div>

              {/* Social Verification OSINT Toggles */}
              <div className="p-3 bg-slate-900/60 rounded-xl border border-white/5 space-y-2">
                <div className="font-bold text-slate-200">Social OSINT Filters</div>
                <div className="space-y-1.5">
                  <label className="flex items-center gap-2 cursor-pointer text-slate-300">
                    <input
                      type="checkbox"
                      checked={settings.requireTwitter}
                      onChange={(e) => setSettings({ ...settings, requireTwitter: e.target.checked })}
                      className="rounded border-slate-700 text-emerald-500 focus:ring-0"
                    />
                    <span>Require Verified Twitter / X Handle</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer text-slate-300">
                    <input
                      type="checkbox"
                      checked={settings.requireTelegram}
                      onChange={(e) => setSettings({ ...settings, requireTelegram: e.target.checked })}
                      className="rounded border-slate-700 text-emerald-500 focus:ring-0"
                    />
                    <span>Require Telegram Community Link</span>
                  </label>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center justify-between pt-2 border-t border-white/10">
              <button
                onClick={() => {
                  setSettings(DEFAULT_SETTINGS);
                  showToast('Reset settings to defaults');
                }}
                className="text-slate-400 hover:text-slate-200 text-xs font-mono"
              >
                Reset Defaults
              </button>
              <button
                onClick={() => {
                  setIsSettingsOpen(false);
                  showToast('Strategy configuration saved');
                }}
                className="px-5 py-2 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs rounded-xl shadow-lg"
              >
                Save &amp; Apply
              </button>
            </div>
          </div>
        </div>
      )}

      {/* STANDALONE SINGLE-FILE HTML EXPORT MODAL */}
      {isExportOpen && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0e121b] border border-white/20 rounded-2xl max-w-2xl w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <div className="flex items-center gap-2">
                <FileCode className="w-5 h-5 text-purple-400" />
                <h3 className="font-extrabold text-base text-white tracking-wide font-mono">
                  STANDALONE SINGLE-FILE HTML EXPORT
                </h3>
              </div>
              <button
                onClick={() => setIsExportOpen(false)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              This dashboard is 100% self-contained with embedded Tailwind CDN, Lucide CDN, and vanilla client-side simulation logic.
              Download or copy the raw single-file HTML code to double-click and run in any web browser without build tools or dependencies!
            </p>

            <div className="flex items-center gap-3 pt-2">
              <button
                onClick={() => {
                  const htmlContent = document.documentElement.outerHTML;
                  const blob = new Blob([htmlContent], { type: 'text/html' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = 'solana-shitcoin-sniper-bot.html';
                  a.click();
                  URL.revokeObjectURL(url);
                  showToast('Downloaded solana-shitcoin-sniper-bot.html!');
                }}
                className="flex-1 py-3 bg-gradient-to-r from-emerald-500 to-cyan-400 hover:from-emerald-400 hover:to-cyan-300 text-slate-950 font-extrabold text-xs rounded-xl shadow-lg flex items-center justify-center gap-2 transition-all cursor-pointer"
              >
                <Download className="w-4 h-4" />
                <span>Download Standalone .html File</span>
              </button>
              <button
                onClick={() => {
                  copyToClipboard(document.documentElement.outerHTML, 'Standalone HTML Code');
                }}
                className="py-3 px-4 bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold text-xs rounded-xl border border-white/10 flex items-center gap-2 cursor-pointer"
              >
                <Copy className="w-4 h-4" />
                <span>Copy Raw Code</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
