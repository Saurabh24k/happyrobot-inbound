// src/pages/Dashboard.tsx
import { useEffect, useMemo, useState, useCallback } from 'react';
import {
  Box, Heading, Text, Input, InputGroup, InputLeftAddon, Button,
  HStack, VStack, SimpleGrid, Badge, Tooltip, Skeleton, Progress,
} from '@chakra-ui/react';
import { RepeatIcon } from '@chakra-ui/icons';
import { format, parseISO } from 'date-fns';
import {
  ResponsiveContainer, LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip as ReTooltip,
  PieChart, Pie, Cell, Label as ReLabel,
} from 'recharts';
import axios, { AxiosError } from 'axios';

// ----------------------------- Types ----------------------------
type Summary = {
  totals: { calls: number; booked: number; no_agreement: number; no_match: number; failed_auth: number; abandoned: number; };
  rates: { avg_board: number | null; avg_agreed: number | null; avg_delta: number | null };
  sentiment: { positive: number; neutral: number; negative: number };
  by_equipment: Array<{ equipment_type: string; booked: number; avg_rate: number | null }>;
  timeseries: Array<{ date: string; calls: number; booked: number }>;
};

type DbUsage = {
  driver?: string | null;
  database?: string | null;
  percent_used?: number | string | null;
  bytes_used?: number | string | null;
  bytes_limit?: number | string | null;
  last_event_at?: string | number | Date | null;
};

// ----------------------------- Utils ----------------------------
const LS_DASH_RANGE = 'dashRange'; // '7' | '30' | 'mtd'

function fmtCurrency(x: number | null | undefined) {
  if (x == null || Number.isNaN(x)) return '—';
  return `$${x.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}
function lastNDays(n: number) {
  const now = new Date();
  const until = format(now, 'yyyy-MM-dd');
  const since = format(new Date(now.getTime() - (n - 1) * 86400000), 'yyyy-MM-dd');
  return { since, until };
}
function monthToDate() {
  const now = new Date();
  return {
    since: format(new Date(now.getFullYear(), now.getMonth(), 1), 'yyyy-MM-dd'),
    until: format(now, 'yyyy-MM-dd'),
  };
}

// Settings overrides used by the Settings page
const KEY_BASE_CANDIDATES = ['api.base', 'hr.api.base', 'API_BASE_URL'];
const KEY_KEYNAME_CANDIDATES = ['api.keyHeader', 'hr.api.keyHeader']; // default x-api-key
const KEY_KEY_CANDIDATES = ['api.key', 'hr.api.key', 'API_KEY'];

function getFromLocalStorage(keys: string[]): string | null {
  for (const k of keys) {
    const v = window.localStorage.getItem(k);
    if (v) return v;
  }
  return null;
}

function resolveApiConfig() {
  const base = getFromLocalStorage(KEY_BASE_CANDIDATES) || '';
  const keyHeader = getFromLocalStorage(KEY_KEYNAME_CANDIDATES) || 'x-api-key';
  const key = getFromLocalStorage(KEY_KEY_CANDIDATES) || '';
  return { base, keyHeader, key };
}

function createApi() {
  const { base, keyHeader, key } = resolveApiConfig();
  const client = axios.create({
    baseURL: base || undefined,
    headers: { 'content-type': 'application/json', ...(key ? { [keyHeader]: key } : {}) },
  });
  return client;
}

// GET with cache-bust using a page-local axios instance
async function getNoCache<T = any>(url: string, params?: Record<string, any>) {
  const client = createApi();
  const { data } = await client.get<T>(url, { params: { ...(params || {}), _ts: Date.now() } });
  return data;
}

// Helpers for DB usage
const toPct = (v: unknown): number => {
  const n = typeof v === 'number' ? v : Number(v);
  if (!Number.isFinite(n)) return 0;
  return n <= 1 ? Math.round(n * 100) : Math.max(0, Math.min(100, Math.round(n)));
};
const toDate = (v: unknown): Date | null => {
  if (v == null) return null;
  if (v instanceof Date && !isNaN(v.valueOf())) return v;
  if (typeof v === 'string') {
    const iso = parseISO(v);
    if (!isNaN(iso.valueOf())) return iso;
    const d = new Date(v);
    return isNaN(d.valueOf()) ? null : d;
  }
  if (typeof v === 'number') {
    const d = new Date(v > 1e12 ? v : v * 1000);
    return isNaN(d.valueOf()) ? null : d;
  }
  return null;
};

// ----------------------------- Small components -----------------------------
function Card({ title, subtitle, children }: { title?: string; subtitle?: string; children: React.ReactNode; }) {
  return (
    <Box borderWidth="1px" rounded="lg" p={4} bg="white" _dark={{ bg: 'gray.800' }}>
      {(title || subtitle) && (
        <VStack align="start" spacing={0.5} mb={3}>
          {title ? <Heading size="sm">{title}</Heading> : null}
          {subtitle ? <Text color="gray.500" fontSize="sm">{subtitle}</Text> : null}
        </VStack>
      )}
      {children}
    </Box>
  );
}
function EmptyState({ message }: { message: string }) {
  return (
    <HStack h="220px" align="center" justify="center">
      <Text color="gray.500">{message}</Text>
    </HStack>
  );
}

// ----------------------------- Page ---------------------------------
export default function Dashboard() {
  // Range state
  const initial = useMemo(() => lastNDays(7), []);
  const [since, setSince] = useState(initial.since);
  const [until, setUntil] = useState(initial.until);
  const [preset, setPreset] = useState<'7' | '30' | 'mtd'>(
    (window.localStorage.getItem(LS_DASH_RANGE) as '7' | '30' | 'mtd') || '7'
  );

  // Summary
  const [summary, setSummary] = useState<Summary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isFetching, setIsFetching] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = useCallback(async (silent = false) => {
    try {
      if (!silent) setIsLoading(true);
      setIsFetching(true);
      setError(null);
      const data = await getNoCache<Summary>('/analytics/summary', { since, until });
      setSummary(data ?? ({} as any));
    } catch (e) {
      const ax = e as AxiosError;
      setError(`Summary error: ${ax.response?.status ?? ''} ${ax.message}`);
      setSummary(null);
    } finally {
      setIsLoading(false);
      setIsFetching(false);
    }
  }, [since, until]);

  const refetch = useCallback(() => fetchSummary(true), [fetchSummary]);

  // DB usage
  const [db, setDb] = useState<DbUsage | null>(null);
  const [dbLoading, setDbLoading] = useState(false);
  const [dbError, setDbError] = useState<string | null>(null);

  const fetchDb = useCallback(async () => {
    try {
      setDbLoading(true);
      setDbError(null);
      const raw = await getNoCache<any>('/analytics/db_usage');
      const data: DbUsage = {
        driver: raw?.driver ?? 'PostgreSQL',
        database: raw?.database ?? raw?.db ?? null,
        percent_used: raw?.percent_used ?? raw?.storage_percent ?? raw?.usage_percent ?? null,
        bytes_used: raw?.bytes_used ?? raw?.used_bytes ?? null,
        bytes_limit: raw?.bytes_limit ?? raw?.limit_bytes ?? null,
        last_event_at: raw?.last_event_at ?? raw?.last_write_at ?? raw?.latest_event_at ?? null,
      };
      setDb(data);
    } catch (e) {
      const ax = e as AxiosError;
      setDb(null);
      setDbError(`DB usage error: ${ax.response?.status ?? ''} ${ax.message}`);
    } finally {
      setDbLoading(false);
    }
  }, []);

  // Init range by preset
  useEffect(() => {
    const apply = (r: { since: string; until: string }) => { setSince(r.since); setUntil(r.until); };
    if (preset === 'mtd') apply(monthToDate()); else apply(lastNDays(preset === '7' ? 7 : 30));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // mount

  // Fetch data whenever range changes
  useEffect(() => { fetchSummary(); fetchDb(); }, [since, until, fetchSummary, fetchDb]);

  // Derived
  const timeseries = summary?.timeseries ?? [];
  const callsTotal = summary?.totals?.calls ?? 0;
  const bookedTotal = summary?.totals?.booked ?? 0;
  const winPctStr = callsTotal ? `${Math.round((bookedTotal / callsTotal) * 100)}%` : '0%';

  const outcomeData = [
    { name: 'Booked', value: summary?.totals?.booked ?? 0, color: '#4F46E5' },   // indigo-600
    { name: 'No Agreement', value: summary?.totals?.no_agreement ?? 0, color: '#F59E0B' }, // amber-500
    { name: 'No Match', value: summary?.totals?.no_match ?? 0, color: '#6B7280' }, // gray-500
    { name: 'Failed Auth', value: summary?.totals?.failed_auth ?? 0, color: '#EF4444' }, // red-500
    { name: 'Abandoned', value: summary?.totals?.abandoned ?? 0, color: '#8B5CF6' }, // violet-500
  ];
  const totalOutcomes = outcomeData.reduce((s, d) => s + (d.value || 0), 0);

  // Config warning
  const cfg = resolveApiConfig();
  const configProblem = !cfg.base ? 'API Base URL is missing' : !cfg.key ? 'API Key is missing' : null;

  const setRange = (range: '7' | '30' | 'mtd') => {
    window.localStorage.setItem(LS_DASH_RANGE, range);
    setPreset(range);
    const r = range === 'mtd' ? monthToDate() : lastNDays(range === '7' ? 7 : 30);
    setSince(r.since); setUntil(r.until);
    setTimeout(() => { refetch(); fetchDb(); }, 0);
  };

  return (
    <Box maxW="1100px" mx="auto" px={{ base: 4, md: 8 }} py={8} display="grid" gap={6}>
      {/* Header + Filters */}
      <HStack justify="space-between" align="center" wrap="wrap" gap={3}>
        <VStack align="start" spacing={1}>
          <Heading size="lg">Dashboard</Heading>
          <Text color="gray.500" fontSize="sm">HappyRobot Carrier Sales</Text>
        </VStack>
        <HStack gap={3} wrap="wrap">
          <InputGroup w="auto" minW="220px">
            <InputLeftAddon>Since</InputLeftAddon>
            <Input
              type="date" value={since}
              onChange={(e) => setSince(e.target.value)}
              onBlur={() => { refetch(); fetchDb(); }}
              max={until}
              aria-label="Since date"
            />
          </InputGroup>
          <InputGroup w="auto" minW="220px">
            <InputLeftAddon>Until</InputLeftAddon>
            <Input
              type="date" value={until}
              onChange={(e) => setUntil(e.target.value)}
              onBlur={() => { refetch(); fetchDb(); }}
              min={since}
              aria-label="Until date"
            />
          </InputGroup>
          <HStack>
            <Button size="sm" variant={preset === '7' ? 'solid' : 'outline'} onClick={() => setRange('7')}>7d</Button>
            <Button size="sm" variant={preset === '30' ? 'solid' : 'outline'} onClick={() => setRange('30')}>30d</Button>
            <Button size="sm" variant={preset === 'mtd' ? 'solid' : 'outline'} onClick={() => setRange('mtd')}>MTD</Button>
          </HStack>
          <Button size="sm" leftIcon={<RepeatIcon />} onClick={() => { refetch(); fetchDb(); }} isDisabled={isFetching}>
            Refresh
          </Button>
        </HStack>
      </HStack>

      {/* Errors / config */}
      {error && (
        <Box borderWidth="1px" borderColor="red.300" bg="red.50" _dark={{ bg: 'red.700', borderColor: 'red.600' }} rounded="md" p={3}>
          <Text fontSize="sm">{error}</Text>
        </Box>
      )}
      {configProblem && (
        <Box borderWidth="1px" borderColor="orange.300" bg="orange.50" _dark={{ bg: 'orange.700', borderColor: 'orange.600' }} rounded="md" p={3}>
          <Text fontSize="sm">Settings issue: {configProblem}. Open the Settings page and set API Base URL and API Key.</Text>
        </Box>
      )}

      {/* KPIs (simple) */}
      <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
        <Card title="Calls">
          <Heading size="lg">{callsTotal}</Heading>
        </Card>
        <Card title="Booked">
          <Heading size="lg">{bookedTotal}</Heading>
        </Card>
        <Card title="Win %">
          <Heading size="lg">{winPctStr}</Heading>
        </Card>
        <Card title="Avg Agreed">
          <Heading size="lg">{fmtCurrency(summary?.rates?.avg_agreed ?? null)}</Heading>
        </Card>
      </SimpleGrid>

      {/* Trends */}
      <Card title="Volume & Bookings" subtitle="Daily calls vs. booked loads">
        {isLoading ? (
          <Skeleton h="320px" rounded="md" />
        ) : timeseries.length === 0 ? (
          <EmptyState message="No data for the selected range." />
        ) : (
          <Box h="320px">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={timeseries as any}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tickFormatter={(d) => format(parseISO(d as string), 'MMM d')} />
                <YAxis allowDecimals={false} />
                <ReTooltip
                  contentStyle={{ borderRadius: 12, borderColor: '#e2e8f0' }}
                  formatter={(value: any, name: any) => [value, name === 'calls' ? 'Calls' : 'Booked']}
                  labelFormatter={(l) => format(parseISO(String(l)), 'EEE, MMM d')}
                />
                <Line type="monotone" dataKey="calls" stroke="#2563eb" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="booked" stroke="#7c3aed" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </Box>
        )}
      </Card>

      {/* Outcomes */}
      <Card title="Outcomes" subtitle="Share of call outcomes">
        <Box h="320px">
          {isLoading ? (
            <Skeleton h="100%" rounded="md" />
          ) : totalOutcomes === 0 ? (
            <EmptyState message="No outcomes recorded." />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={outcomeData as any} dataKey="value" nameKey="name" innerRadius="55%" outerRadius="85%" paddingAngle={2}>
                  {outcomeData.map((d, i) => <Cell key={i} fill={d.color} />)}
                  <ReLabel value={`${winPctStr} win`} position="center" />
                </Pie>
                <ReTooltip
                  contentStyle={{ borderRadius: 12, borderColor: '#e2e8f0' }}
                  formatter={(v: any, n: any) => [`${v}`, n]}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </Box>
      </Card>

      {/* Data Source */}
      <Card title="Data Source" subtitle="Render Postgres usage & last write">
        {dbLoading && <Skeleton h="80px" rounded="md" />}
        {!dbLoading && db && (
          <VStack align="stretch" gap={3}>
            <HStack justify="space-between" wrap="wrap">
              <Text fontSize="sm" color="gray.600">
                {(db.driver || 'PostgreSQL')}{db.database ? ` • ${db.database}` : ''}
              </Text>
              <Text fontSize="sm" color="gray.600">
                {Number.isFinite(Number(db.percent_used)) ? `${toPct(db.percent_used)}% used` : '—'}
              </Text>
            </HStack>
            <Progress
              value={toPct(db.percent_used)}
              colorScheme={toPct(db.percent_used) > 85 ? 'red' : toPct(db.percent_used) > 70 ? 'orange' : 'purple'}
              rounded="full"
              height="10px"
            />
            <HStack justify="space-between" wrap="wrap">
              <Text fontSize="sm" color="gray.500">
                {(() => {
                  const d = toDate(db.last_event_at);
                  return `Last event: ${d ? format(d, 'PPpp') : '—'}`;
                })()}
              </Text>
              <Button size="sm" variant="outline" leftIcon={<RepeatIcon />} onClick={fetchDb}>
                Refresh Source
              </Button>
            </HStack>
          </VStack>
        )}
        {!dbLoading && !db && (
          <VStack align="start" gap={2}>
            <Text fontSize="sm" color="red.500">Couldn’t load DB usage.</Text>
            {dbError && <Text fontSize="xs" color="gray.500">{dbError}</Text>}
          </VStack>
        )}
      </Card>
    </Box>
  );
}
