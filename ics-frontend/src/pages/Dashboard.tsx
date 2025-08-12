// src/pages/Dashboard.tsx
import { useEffect, useMemo, useState, useCallback } from 'react';
import {
  Box, Heading, Text, Input, InputGroup, InputLeftAddon, Button,
  HStack, VStack, SimpleGrid, Badge, Tooltip, useToast, Divider,
  Tag, TagLabel, TagLeftIcon, useColorModeValue, useToken, Skeleton,
  Progress, Switch, FormControl, FormLabel,
} from '@chakra-ui/react';
import { keyframes } from '@emotion/react';
import {
  RepeatIcon, DownloadIcon, TriangleUpIcon, TriangleDownIcon,
  TimeIcon, InfoOutlineIcon, ViewIcon, ViewOffIcon,
} from '@chakra-ui/icons';
import { format, parseISO } from 'date-fns';
import {
  ResponsiveContainer, LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip as ReTooltip,
  PieChart, Pie, Cell, Label as ReLabel, BarChart, Bar, AreaChart, Area,
} from 'recharts';
import { useSummary } from '../api/hooks';
import { api } from '../api/client';

// ----------------------------- Types ----------------------------
type Summary = {
  totals: { calls: number; booked: number; no_agreement: number; no_match: number; failed_auth: number; abandoned: number; };
  rates: { avg_board: number | null; avg_agreed: number | null; avg_delta: number | null };
  sentiment: { positive: number; neutral: number; negative: number };
  by_equipment: Array<{ equipment_type: string; booked: number; avg_rate: number | null }>;
  timeseries: Array<{ date: string; calls: number; booked: number }>;
};

type DbUsage = {
  driver: string;
  database?: string | null;
  percent_used?: number | null;
  bytes_used?: number | null;
  bytes_limit?: number | null;
  last_event_at?: string | null;
};

// ----------------------------- Utils ----------------------------
const LS_DASH_RANGE = 'dashRange'; // '7' | '30' | 'mtd'
const LS_LIVE = 'dashLive';        // '1' | '0'

const fadeUp = keyframes`from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}`;
const fadeIn = keyframes`from{opacity:0}to{opacity:1}`;

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
function toCSV(rows: Record<string, unknown>[], headerOrder?: string[]) {
  if (!rows || rows.length === 0) return '';
  const headers = headerOrder ?? Object.keys(rows[0]);
  const esc = (v: unknown) => {
    const s = v == null ? '' : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [headers.join(','), ...rows.map((r) => headers.map((h) => esc((r as any)[h])).join(','))];
  return lines.join('\n');
}
function downloadFile(filename: string, content: string, mime = 'text/csv;charset=utf-8') {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}
function percentChange(series?: number[]) {
  if (!series || series.length < 2) return null;
  const first = series[0]; const last = series[series.length - 1];
  if (first === 0 && last === 0) return 0;
  if (first === 0) return null;
  return ((last - first) / Math.abs(first)) * 100;
}

// ----------------------------- Small components -----------------------------
// function Pill({
//   label, scheme, icon,
// }: { label: string; scheme: 'green' | 'red' | 'gray' | 'blue' | 'purple' | 'orange'; icon: any; }) {
//   return (
//     <Tag size="sm" colorScheme={scheme} variant="subtle" rounded="full">
//       <TagLeftIcon as={icon} />
//       <TagLabel>{label}</TagLabel>
//     </Tag>
//   );
// }
function EmptyState({ message }: { message: string }) {
  const fg = useColorModeValue('gray.600', 'gray.400');
  return (
    <HStack h="220px" align="center" justify="center">
      <Text color={fg}>{message}</Text>
    </HStack>
  );
}
function Card({ title, subtitle, children }: { title?: string; subtitle?: string; children: React.ReactNode; }) {
  const border = useColorModeValue('blackAlpha.200', 'whiteAlpha.200');
  const shadow = useColorModeValue('sm', 'dark-lg');
  const hoverShadow = useColorModeValue('md', 'xl');
  const bg = useColorModeValue('white', 'gray.800');

  return (
    <Box
      borderWidth="1px" borderColor={border} rounded="2xl"
      p={{ base: 4, md: 6 }} bg={bg} position="relative" boxShadow={shadow}
      transition="transform 140ms ease, box-shadow 140ms ease"
      _hover={{ transform: 'translateY(-2px)', boxShadow: hoverShadow }}
    >
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
function ToggleChip({ active, label, onClick }: { active: boolean; label: string; onClick: () => void; }) {
  return (
    <Tag
      size="md" colorScheme={active ? 'purple' : 'gray'} variant={active ? 'solid' : 'subtle'}
      cursor="pointer" onClick={onClick} rounded="full" aria-pressed={active} role="button" px={3}
    >
      <TagLeftIcon as={active ? ViewIcon : ViewOffIcon} />
      <TagLabel>{label}</TagLabel>
    </Tag>
  );
}
function RangeTag({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <Tag
      size="md" colorScheme={active ? 'purple' : 'gray'} variant={active ? 'solid' : 'subtle'}
      cursor="pointer" onClick={onClick} rounded="full" aria-pressed={active} px={3}
    >
      <TagLabel>{label}</TagLabel>
    </Tag>
  );
}

// Unified donut with center label + hover highlight
function Donut({
  data, inner = '55%', outer = '85%', centerLabel,
}: {
  data: Array<{ name: string; value: number; color: string }>;
  inner?: string | number;
  outer?: string | number;
  centerLabel: string;
}) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie data={data as any} dataKey="value" nameKey="name" innerRadius={inner} outerRadius={outer} paddingAngle={2}>
          {data.map((d, i) => <Cell key={i} fill={d.color} />)}
          <ReLabel value={centerLabel} position="center" />
        </Pie>
        <ReTooltip
          contentStyle={{ borderRadius: 12, borderColor: '#e2e8f0' }}
          formatter={(v: any, n: any) => [`${v}`, n]}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

// Small live stat chip (only renders when we actually have data)
function StatChip({ label, value }: { label: string; value: string | number }) {
  return (
    <Tag size="sm" variant="subtle" rounded="full" colorScheme="gray">
      <TagLeftIcon as={InfoOutlineIcon} />
      <TagLabel>
        {label}: {value}
      </TagLabel>
    </Tag>
  );
}

// ----------------------------- Page ---------------------------------
export default function Dashboard() {
  const [blue700, blue600, blue500, purple500, orange500, gray500, red500] = useToken('colors',
    ['blue.700', 'blue.600', 'blue.500', 'purple.500', 'orange.500', 'gray.500', 'red.500']);

  const axisFg = useColorModeValue('#0f172a', '#cbd5e1');
  const gridColor = useColorModeValue('#e2e8f0', '#334155');
  const bannerBg = useColorModeValue('gray.50', 'gray.700');
  const bannerBorder = useColorModeValue('gray.200', 'gray.600');
  const bannerIconColor = useColorModeValue('blue.600', 'blue.300');
  const toast = useToast();

  // Range state
  const initial = useMemo(() => lastNDays(7), []);
  const [since, setSince] = useState(initial.since);
  const [until, setUntil] = useState(initial.until);
  const [preset, setPreset] = useState<'7' | '30' | 'mtd'>(
    (window.localStorage.getItem(LS_DASH_RANGE) as '7' | '30' | 'mtd') || '7'
  );
  const [live, setLive] = useState<boolean>((window.localStorage.getItem(LS_LIVE) || '0') === '1');

  // Data
  const { data, isLoading, error, refetch, isFetching } = useSummary(since, until);
  const summary = (data ?? {}) as Summary;

  // DB usage (purposeful: verify backend wiring)
  const [db, setDb] = useState<DbUsage | null>(null);
  const [dbLoading, setDbLoading] = useState(false);
  const fetchDb = useCallback(async () => {
    try {
      setDbLoading(true);
      const res = await api.get('/analytics/db_usage');
      setDb(res.data || null);
    } catch {
      setDb(null);
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

  // Auto refresh
  useEffect(() => {
    if (!live) return;
    const id = setInterval(() => { refetch(); fetchDb(); }, 10000);
    return () => clearInterval(id);
  }, [live, refetch, fetchDb]);

  // Refresh DB usage on mount & range changes
  useEffect(() => { fetchDb(); }, [since, until, fetchDb]);

  // Derived
  const timeseries = summary?.timeseries ?? [];
  const byEq = summary?.by_equipment ?? [];

  const callsSeries = timeseries.map((d) => d.calls);
  const bookedSeries = timeseries.map((d) => d.booked);
  const winSeries = timeseries.map((d) => (d.calls ? Math.round((d.booked / d.calls) * 100) : 0));

  const callsTotal = summary?.totals?.calls ?? 0;
  const bookedTotal = summary?.totals?.booked ?? 0;
  const winPctStr = callsTotal ? `${Math.round((bookedTotal / callsTotal) * 100)}%` : '0%';

  const outcomeData = [
    { name: 'Booked', value: summary?.totals?.booked ?? 0, color: blue600 },
    { name: 'No Agreement', value: summary?.totals?.no_agreement ?? 0, color: orange500 },
    { name: 'No Match', value: summary?.totals?.no_match ?? 0, color: gray500 },
    { name: 'Failed Auth', value: summary?.totals?.failed_auth ?? 0, color: red500 },
    { name: 'Abandoned', value: summary?.totals?.abandoned ?? 0, color: purple500 },
  ];
  const totalOutcomes = outcomeData.reduce((s, d) => s + (d.value || 0), 0);

  // ✅ End label should follow the selected "until" date
  const endLabel = useMemo(() => {
    const d = until || (timeseries.length ? timeseries[timeseries.length - 1].date : null);
    try {
      return d ? format(parseISO(d), 'MMM d').toUpperCase() : null;
    } catch {
      return null;
    }
  }, [until, timeseries]);

  // Actions
  const setRange = (range: '7' | '30' | 'mtd') => {
    window.localStorage.setItem(LS_DASH_RANGE, range);
    setPreset(range);
    const r = range === 'mtd' ? monthToDate() : lastNDays(range === '7' ? 7 : 30);
    setSince(r.since); setUntil(r.until);
    // Kick a fetch so chips + charts update immediately
    setTimeout(() => { refetch(); fetchDb(); }, 0);
  };
  const exportCSV = () => {
    const csv = toCSV(timeseries, ['date', 'calls', 'booked']);
    if (!csv) return toast({ status: 'info', title: 'No data to export.' });
    downloadFile(`summary_${since}_to_${until}.csv`, csv);
  };

  const hasError = !!error;
  const showPerfChips = !isLoading && (timeseries.length > 0 || callsTotal > 0 || bookedTotal > 0);

  return (
    <Box maxW="1100px" mx="auto" px={{ base: 4, md: 8 }} py={10} display="grid" gap={6} animation={`${fadeIn} .25s ease`}>
      {/* Performance bar (only real data; no dummies) */}
      <Box
        borderWidth="1px" borderColor={bannerBorder} bg={bannerBg} rounded="2xl"
        p={{ base: 4, md: 5 }} display="grid" gap={3}
        gridTemplateColumns={{ base: '1fr', md: '1fr auto auto auto' }}
        alignItems="center" animation={`${fadeUp} .28s ease`}
      >
        <HStack spacing={3} align="center" minW={0}>
          <Box as={TimeIcon} color={bannerIconColor} boxSize={6} aria-hidden />
          <VStack align="start" spacing={1} minW={0}>
            <Text fontWeight="semibold">Performance</Text>
            {showPerfChips && (
              <HStack spacing={2} mt={1} flexWrap="wrap">
                <StatChip label="Calls" value={callsTotal} />
                <StatChip label="Booked" value={bookedTotal} />
                {callsTotal > 0 && <StatChip label="Win" value={winPctStr} />}
              </HStack>
            )}
          </VStack>
        </HStack>

        <HStack justifySelf={{ md: 'center' }}>
          {endLabel && (
            <Tooltip label="Selected end date">
              <Badge variant="subtle" colorScheme="gray" rounded="full" px={3} py={1} aria-live="polite">
                THROUGH {endLabel}
              </Badge>
            </Tooltip>
          )}
        </HStack>

        <FormControl display="flex" alignItems="center" justifySelf="end">
          <FormLabel htmlFor="live-switch" mb="0" fontSize="sm" color="gray.600">Live</FormLabel>
          <Switch
            id="live-switch" isChecked={live}
            onChange={(e) => {
              const val = e.target.checked;
              setLive(val);
              window.localStorage.setItem(LS_LIVE, val ? '1' : '0');
              if (val) { refetch(); fetchDb(); }
            }}
            colorScheme="purple"
          />
        </FormControl>

        <HStack justifySelf="end" spacing={2}>
          <Button size="sm" variant="outline" leftIcon={<RepeatIcon />} onClick={() => { refetch(); fetchDb(); }} isDisabled={isFetching}>
            Refresh
          </Button>
          <Button size="sm" variant="outline" leftIcon={<DownloadIcon />} onClick={exportCSV}>
            Export CSV
          </Button>
        </HStack>
      </Box>

      {/* Header + Filters */}
      <HStack justify="space-between" align="center" animation={`${fadeUp} .3s ease .02s both`} wrap="wrap" gap={3}>
        <VStack align="start" spacing={1}>
          <Heading size="lg" letterSpacing="-0.02em">Dashboard</Heading>
          <Text color="gray.500" fontSize="sm">HappyRobot Carrier Sales</Text>
        </VStack>
        <HStack gap={3} wrap="wrap">
          <InputGroup w="auto" minW="220px">
            <InputLeftAddon>Since</InputLeftAddon>
            <Input
              type="date" value={since}
              onChange={(e) => setSince(e.target.value)}
              onBlur={() => { refetch(); fetchDb(); }}
              max={until} aria-label="Since date"
            />
          </InputGroup>
          <InputGroup w="auto" minW="220px">
            <InputLeftAddon>Until</InputLeftAddon>
            <Input
              type="date" value={until}
              onChange={(e) => setUntil(e.target.value)}
              onBlur={() => { refetch(); fetchDb(); }}
              min={since} aria-label="Until date"
            />
          </InputGroup>
          <HStack>
            <RangeTag active={preset === '7'} label="7d" onClick={() => setRange('7')} />
            <RangeTag active={preset === '30'} label="30d" onClick={() => setRange('30')} />
            <RangeTag active={preset === 'mtd'} label="MTD" onClick={() => setRange('mtd')} />
          </HStack>
        </HStack>
      </HStack>

      {hasError && (
        <Box borderWidth="1px" borderColor="red.300" bg="red.50" _dark={{ bg: 'red.700', borderColor: 'red.600' }} rounded="lg" p={3}>
          <Text fontSize="sm">Data error — try a different range or refresh.</Text>
        </Box>
      )}

      {/* KPIs (lean, useful) */}
      <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
        <Kpi title="Calls" value={summary?.totals?.calls ?? 0} series={callsSeries} />
        <Kpi title="Booked" value={summary?.totals?.booked ?? 0} series={bookedSeries} />
        <Kpi title="Win %" value={winPctStr} series={winSeries} isPercent />
        <Kpi title="Avg Agreed" value={fmtCurrency(summary?.rates?.avg_agreed)} />
      </SimpleGrid>

      {/* Trends & Outcomes */}
      <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
        <Card title="Volume & Bookings" subtitle="Daily calls vs. booked loads">
          {isLoading ? (
            <Skeleton h="320px" rounded="md" />
          ) : timeseries.length === 0 ? (
            <EmptyState message="No data for the selected range." />
          ) : (
            <Box h="320px" animation={`${fadeUp} .32s ease`}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={timeseries as any}>
                  <defs>
                    <linearGradient id="gradCalls" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={blue700} stopOpacity={0.95} />
                      <stop offset="100%" stopColor={blue700} stopOpacity={0.15} />
                    </linearGradient>
                    <linearGradient id="gradBooked" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={purple500} stopOpacity={0.95} />
                      <stop offset="100%" stopColor={purple500} stopOpacity={0.18} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                  <XAxis dataKey="date" tickFormatter={(d) => format(parseISO(d as string), 'MMM d')} stroke={axisFg} tickLine={false} />
                  <YAxis allowDecimals={false} stroke={axisFg} tickLine={false} axisLine={false} />
                  <ReTooltip
                    contentStyle={{ borderRadius: 12, borderColor: '#e2e8f0' }}
                    formatter={(value: any, name: any) => [value, name === 'calls' ? 'Calls' : 'Booked']}
                    labelFormatter={(l) => format(parseISO(String(l)), 'EEE, MMM d')}
                  />
                  <Line type="monotone" dataKey="calls" stroke="url(#gradCalls)" dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="booked" stroke="url(#gradBooked)" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </Box>
          )}
          <Divider my={4} />
          <HStack gap={2} justify="flex-end">
            <ToggleChip active label="Show Calls" onClick={() => { /* always on for clarity */ }} />
            <ToggleChip active label="Show Booked" onClick={() => { /* always on for clarity */ }} />
          </HStack>
        </Card>

        <Card title="Outcomes" subtitle="Share of call outcomes">
          <Box h="320px" animation={`${fadeUp} .34s ease`}>
            {isLoading ? (
              <Skeleton h="100%" rounded="md" />
            ) : totalOutcomes === 0 ? (
              <EmptyState message="No outcomes recorded." />
            ) : (
              <Donut data={outcomeData} centerLabel={`${winPctStr} win`} />
            )}
          </Box>
        </Card>
      </SimpleGrid>

      {/* Sentiment & Equipment */}
      <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
        <Card title="Sentiment" subtitle="End-of-call tone">
          <HStack justify="space-between" align="start" gap={4}>
            <Box h="260px" w="260px" animation={`${fadeUp} .36s ease`}>
              {isLoading ? (
                <Skeleton h="100%" rounded="md" />
              ) : (
                <Donut
                  data={[
                    { name: 'Positive', value: summary?.sentiment?.positive ?? 0, color: blue500 },
                    { name: 'Neutral', value: summary?.sentiment?.neutral ?? 0, color: gray500 },
                    { name: 'Negative', value: summary?.sentiment?.negative ?? 0, color: red500 },
                  ]}
                  centerLabel={`${(() => {
                    const p = summary?.sentiment?.positive ?? 0;
                    const t = p + (summary?.sentiment?.neutral ?? 0) + (summary?.sentiment?.negative ?? 0);
                    return t ? Math.round((p / t) * 100) : 0;
                  })()}%`}
                />
              )}
            </Box>
            <VStack align="start" gap={2} minW="180px">
              <Badge variant="subtle" colorScheme="blue">Positive: {summary?.sentiment?.positive ?? 0}</Badge>
              <Badge variant="subtle" colorScheme="gray">Neutral: {summary?.sentiment?.neutral ?? 0}</Badge>
              <Badge variant="subtle" colorScheme="red">Negative: {summary?.sentiment?.negative ?? 0}</Badge>
            </VStack>
          </HStack>
        </Card>

        <Card title="Booked by Equipment" subtitle="Where wins come from">
          {isLoading ? (
            <Skeleton h="300px" rounded="md" />
          ) : byEq.length === 0 ? (
            <EmptyState message="No equipment data." />
          ) : (
            <Box h="300px" animation={`${fadeUp} .38s ease`}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={byEq as any}>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                  <XAxis dataKey="equipment_type" stroke={axisFg} tickLine={false} />
                  <YAxis allowDecimals={false} stroke={axisFg} tickLine={false} axisLine={false} />
                  <ReTooltip contentStyle={{ borderRadius: 12, borderColor: '#e2e8f0' }} />
                  <Bar dataKey="booked" fill={blue600} radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Box>
          )}
        </Card>
      </SimpleGrid>

      {/* Data Source */}
      <Card title="Data Source" subtitle="Render Postgres usage & last write">
        {dbLoading && <Skeleton h="80px" rounded="md" />}
        {!dbLoading && db && (
          <VStack align="stretch" gap={3}>
            <HStack justify="space-between" wrap="wrap">
              <Text fontSize="sm" color="gray.600">
                {db.driver}{db.database ? ` • ${db.database}` : ''}
              </Text>
              <Text fontSize="sm" color="gray.600">
                {typeof db.percent_used === 'number' ? `${Math.round(db.percent_used)}% used` : '—'}
              </Text>
            </HStack>
            <Progress
              value={typeof db.percent_used === 'number' ? db.percent_used : 0}
              colorScheme={
                db.percent_used && db.percent_used > 85 ? 'red'
                : db.percent_used && db.percent_used > 70 ? 'orange'
                : 'purple'
              }
              rounded="full"
              height="10px"
            />
            <HStack justify="space-between" wrap="wrap">
              <Text fontSize="sm" color="gray.500">
                Last event: {db.last_event_at ? format(parseISO(db.last_event_at), 'PPpp') : '—'}
              </Text>
              <Button size="sm" variant="outline" leftIcon={<RepeatIcon />} onClick={fetchDb}>
                Refresh Source
              </Button>
            </HStack>
          </VStack>
        )}
        {!dbLoading && !db && <Text fontSize="sm" color="red.500">Couldn’t load DB usage.</Text>}
      </Card>
    </Box>
  );
}

// ----------------------------- KPI Card ------------------------------
function Kpi({ title, value, series, isPercent }: { title: string; value: string | number; series?: number[]; isPercent?: boolean; }) {
  const change = percentChange(series);
  return (
    <Box
      borderWidth="1px" rounded="2xl" p={4} bg="white" _dark={{ bg: 'gray.800' }}
      animation={`${fadeUp} .28s ease`} transition="transform 140ms ease, box-shadow 140ms ease"
      _hover={{ transform: 'translateY(-2px)', boxShadow: 'md' }}
    >
      <VStack align="stretch" gap={3}>
        <HStack justify="space-between" align="start">
          <Text fontSize="sm" color="gray.500">{title}</Text>
          {change != null && (
            <HStack gap={1} px={2} py={0.5} rounded="full" bg={{ base: 'blackAlpha.50', _dark: 'whiteAlpha.100' }}
              borderWidth="1px" borderColor={{ base: 'blackAlpha.200', _dark: 'whiteAlpha.200' }}>
              {change >= 0 ? <TriangleUpIcon color="green.500" boxSize={3} /> : <TriangleDownIcon color="red.500" boxSize={3} />}
              <Text fontSize="xs" color={change >= 0 ? 'green.600' : 'red.500'}>{Math.abs(Math.round(change))}%</Text>
            </HStack>
          )}
        </HStack>

        <HStack justify="space-between" align="end">
          <HStack align="baseline" gap={2}>
            <Text fontSize="3xl" fontWeight="semibold" bgGradient="linear(to-r, blue.600, purple.500)" bgClip="text" lineHeight="1">
              {value}{isPercent && typeof value === 'string' ? '' : ''}
            </Text>
          </HStack>

          {series && series.length > 1 ? (
            <Box w="140px" h="44px">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={series.map((y, i) => ({ i, y })) as any}>
                  <defs>
                    <linearGradient id="spark" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#2563eb" stopOpacity={0.65} />
                      <stop offset="100%" stopColor="#7c3aed" stopOpacity={0.06} />
                    </linearGradient>
                  </defs>
                  <Area type="monotone" dataKey="y" stroke="#2563eb" fill="url(#spark)" />
                </AreaChart>
              </ResponsiveContainer>
            </Box>
          ) : <Box w="140px" h="44px" />}
        </HStack>
      </VStack>
    </Box>
  );
}
