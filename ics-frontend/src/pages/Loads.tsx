import { useMemo, useState } from 'react';
import {
  Box,
  Heading,
  Text,
  HStack,
  VStack,
  SimpleGrid,
  Select,
  Input,
  InputGroup,
  InputLeftAddon,
  Button,
  IconButton,
  Badge,
  Tooltip,
  useToast,
  Skeleton,
  Divider,
  Kbd,
  Code,
} from '@chakra-ui/react';
import {
  SearchIcon,
  RepeatIcon,
  ExternalLinkIcon,
  DownloadIcon,
  InfoOutlineIcon,
  LinkIcon,
  CopyIcon,
} from '@chakra-ui/icons';
import { FormControl, FormLabel } from '@chakra-ui/form-control';
import { api, getApiBase } from '../api/client';

type LoadItem = {
  load_id: string;
  origin: string;
  destination: string;
  pickup_datetime: string;
  delivery_datetime: string;
  equipment_type: string;
  loadboard_rate: number;
  notes?: string | null;
  weight?: number | null;
  commodity_type?: string | null;
  num_of_pieces?: number | null;
  miles?: number | null;
  dimensions?: string | null;
};

const CANDIDATE_SEARCH_PATHS = [
  '/search_loads',
  '/api/search_loads',
  '/v1/search_loads',
  '/v1/api/search_loads',
];

const CANDIDATE_OPENAPI_PATHS = [
  '/openapi.json',
  '/api/openapi.json',
  '/v1/openapi.json',
  '/v1/api/openapi.json',
  '/docs',
  '/api/docs',
  '/v1/docs',
  '/v1/api/docs',
];

// ------------------- utils -------------------
function abs(urlPath: string) {
  const base = getApiBase().replace(/\/+$/, '');
  const path = urlPath.startsWith('/') ? urlPath : `/${urlPath}`;
  return `${base}${path}`;
}
function fmtUSD(n?: number | null) {
  if (n == null) return '—';
  try {
    return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  } catch {
    return `$${n}`;
  }
}
function toCSV(rows: Record<string, unknown>[], headerOrder?: string[]) {
  if (!rows?.length) return '';
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
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ------------------- component -------------------
export default function Loads() {
  // form
  const [equipment_type, setEq] = useState('Dry Van');
  const [origin, setOrigin] = useState('Chicago, IL');
  const [destination, setDest] = useState('Dallas, TX');
  const [pickup_window_start, setStart] = useState('2025-08-06T08:00:00');
  const [pickup_window_end, setEnd] = useState('2025-08-07T08:00:00');
  const [limit, setLimit] = useState(10);

  // state
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string>('');
  const [debugUrl, setDebugUrl] = useState<string>('');
  const [rows, setRows] = useState<LoadItem[]>([]);
  const [discovered, setDiscovered] = useState<string[]>([]);
  const [openapiTried, setOpenapiTried] = useState<string[]>([]);
  const [openapiError, setOpenapiError] = useState<string>('');

  // derived
  const apiBase = useMemo(() => getApiBase(), []);
  const foundDocs = useMemo(() => discovered.length > 0 || status.includes('Found docs'), [discovered, status]);

  function resetDefaults() {
    setEq('Dry Van');
    setOrigin('Chicago, IL');
    setDest('Dallas, TX');
    setStart('2025-08-06T08:00:00');
    setEnd('2025-08-07T08:00:00');
    setLimit(10);
    setRows([]);
    setStatus('');
    setDebugUrl('');
  }

  function quickPreset(kind: 'today' | 'tomorrow' | '24h') {
    const now = new Date();
    const pad = (x: number) => String(x).padStart(2, '0');
    const iso = (d: Date) =>
      `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(
        d.getMinutes()
      )}:${pad(d.getSeconds())}`;

    if (kind === 'today') {
      const start = new Date(now);
      start.setHours(8, 0, 0, 0);
      const end = new Date(now);
      end.setHours(20, 0, 0, 0);
      setStart(iso(start));
      setEnd(iso(end));
      return;
    }
    if (kind === 'tomorrow') {
      const start = new Date(now);
      start.setDate(start.getDate() + 1);
      start.setHours(8, 0, 0, 0);
      const end = new Date(start);
      end.setHours(20, 0, 0, 0);
      setStart(iso(start));
      setEnd(iso(end));
      return;
    }
    // 24h
    const start = new Date(now);
    const end = new Date(now.getTime() + 24 * 60 * 60 * 1000);
    setStart(iso(start));
    setEnd(iso(end));
  }

  async function onSearch() {
    setLoading(true);
    setStatus('Searching…');
    setRows([]);
    setDebugUrl('');

    const payload = {
      equipment_type,
      origin,
      destination,
      pickup_window_start,
      pickup_window_end,
      limit,
    };

    let lastErr: any = null;

    for (const path of CANDIDATE_SEARCH_PATHS) {
      const url = abs(path);
      setDebugUrl(url);
      try {
        const { data } = await api.post<{ results: LoadItem[] }>(url, payload);
        const results = data?.results ?? [];
        setRows(results);
        setStatus(`Found ${results.length} load${results.length === 1 ? '' : 's'} via ${path}.`);
        setLoading(false);
        return;
      } catch (e: any) {
        lastErr = e;
      }
    }

    const msg =
      lastErr?.response?.data?.detail ||
      lastErr?.response?.status ||
      lastErr?.message ||
      'Unknown error';
    setStatus(`Error: ${String(msg)} (tried: ${CANDIDATE_SEARCH_PATHS.join(', ')})`);
    setLoading(false);
    toast({
      status: 'error',
      title: 'Search failed',
      description: String(msg),
    });
  }

  async function discoverEndpoints() {
    setDiscovered([]);
    setOpenapiTried([]);
    setOpenapiError('');
    const tried: string[] = [];
    try {
      for (const p of CANDIDATE_OPENAPI_PATHS) {
        const url = abs(p);
        tried.push(url);
        setOpenapiTried([...tried]);
        try {
          const res = await fetch(url, {
            headers: { 'x-api-key': (api.defaults.headers as any)?.['x-api-key'] as string },
          });
          if (!res.ok) continue;

          const ct = res.headers.get('content-type') || '';
          if (ct.includes('application/json')) {
            const json = await res.json();
            if (json && json.paths && typeof json.paths === 'object') {
              const paths = Object.keys(json.paths);
              setDiscovered(paths);
              setStatus(`Discovered ${paths.length} paths from ${p}.`);
              return;
            }
          } else {
            setStatus(`Found docs at ${p}. Open it in a new tab.`);
            setDiscovered([]);
            return;
          }
        } catch {
        }
      }
      setOpenapiError('Could not fetch OpenAPI/docs from any known path.');
    } catch (e: any) {
      setOpenapiError(String(e?.message || e));
    }
  }

  function exportCSV() {
    if (!rows.length) {
      toast({ status: 'info', title: 'No results to export.' });
      return;
    }
    const headers = [
      'load_id',
      'origin',
      'destination',
      'pickup_datetime',
      'delivery_datetime',
      'equipment_type',
      'miles',
      'loadboard_rate',
      'commodity_type',
      'weight',
      'num_of_pieces',
      'dimensions',
      'notes',
    ];
    const csv = toCSV(rows as any[], headers);
    downloadFile('loads.csv', csv);
    toast({ status: 'success', title: 'CSV exported.' });
  }

  function copyPayload() {
    const payload = {
      equipment_type,
      origin,
      destination,
      pickup_window_start,
      pickup_window_end,
      limit,
    };
    navigator.clipboard
      .writeText(JSON.stringify(payload, null, 2))
      .then(() => toast({ status: 'success', title: 'Search payload copied.' }))
      .catch(() => toast({ status: 'error', title: 'Could not copy.' }));
  }

  // ------------------- UI -------------------
  return (
    <Box maxW="1100px" mx="auto" px={{ base: 4, md: 8 }} py={10}>
      {/* Header */}
      <HStack justify="space-between" mb={6}>
        <VStack align="start" spacing={1}>
          <Heading size="lg" lineHeight="short">Loads</Heading>
          <Text color="gray.500" fontSize="sm">
            Search your load service and preview results with a clean, compact layout.
          </Text>
        </VStack>
        <HStack>
          <Tooltip label="Export CSV">
            <IconButton aria-label="Export CSV" icon={<DownloadIcon />} variant="outline" onClick={exportCSV} />
          </Tooltip>
          <Tooltip label="Reset to defaults">
            <IconButton aria-label="Reset" icon={<RepeatIcon />} variant="outline" onClick={resetDefaults} />
          </Tooltip>
        </HStack>
      </HStack>

      {/* Form Card */}
      <Box
        borderWidth="1px"
        bg="white"
        _dark={{ bg: 'gray.800' }}
        rounded="2xl"
        p={{ base: 4, md: 6 }}
        shadow="sm"
        mb={6}
      >
        <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={5}>
          <FormControl>
            <FormLabel>Equipment</FormLabel>
            <Select value={equipment_type} onChange={(e) => setEq(e.target.value)}>
              <option>Dry Van</option>
              <option>Reefer</option>
              <option>Step Deck</option>
              <option>Flatbed</option>
              <option>Tanker</option>
            </Select>
          </FormControl>

          <FormControl>
            <FormLabel>Origin</FormLabel>
            <Input placeholder="City, ST" value={origin} onChange={(e) => setOrigin(e.target.value)} />
          </FormControl>

          <FormControl>
            <FormLabel>Destination</FormLabel>
            <Input placeholder="City, ST" value={destination} onChange={(e) => setDest(e.target.value)} />
          </FormControl>

          <FormControl>
            <FormLabel>Pickup start</FormLabel>
            <InputGroup>
              <InputLeftAddon>ISO</InputLeftAddon>
              <Input value={pickup_window_start} onChange={(e) => setStart(e.target.value)} placeholder="YYYY-MM-DDTHH:mm:ss" />
            </InputGroup>
          </FormControl>

          <FormControl>
            <FormLabel>Pickup end</FormLabel>
            <InputGroup>
              <InputLeftAddon>ISO</InputLeftAddon>
              <Input value={pickup_window_end} onChange={(e) => setEnd(e.target.value)} placeholder="YYYY-MM-DDTHH:mm:ss" />
            </InputGroup>
          </FormControl>

          <FormControl>
            <FormLabel>Limit</FormLabel>
            <Input type="number" min={1} max={50} value={limit} onChange={(e) => setLimit(Number(e.target.value))} />
          </FormControl>
        </SimpleGrid>

        <HStack mt={4} spacing={3} wrap="wrap">
          <Button onClick={onSearch} isDisabled={loading} leftIcon={<SearchIcon />}>
            {loading ? 'Searching…' : 'Search'}
          </Button>
          <Button variant="outline" onClick={discoverEndpoints} leftIcon={<ExternalLinkIcon />}>
            Discover Endpoints
          </Button>
          <Button variant="ghost" onClick={copyPayload} leftIcon={<CopyIcon />}>
            Copy Payload
          </Button>

          <HStack spacing={2} ml={{ base: 0, md: 'auto' }}>
            <Text fontSize="sm" color="gray.500">Quick presets:</Text>
            <Button size="sm" variant="outline" onClick={() => quickPreset('today')}>
              Today <Kbd ml={1}>8–20</Kbd>
            </Button>
            <Button size="sm" variant="outline" onClick={() => quickPreset('tomorrow')}>
              Tomorrow
            </Button>
            <Button size="sm" variant="outline" onClick={() => quickPreset('24h')}>
              Next 24h
            </Button>
          </HStack>
        </HStack>

        {/* subtle status / debug */}
        <HStack mt={3} spacing={3} align="center">
          <InfoOutlineIcon color="gray.400" />
          <Text fontSize="sm" color="gray.600">
            {status || 'Fill the form and press Search.'}
          </Text>
        </HStack>

        {debugUrl && (
          <HStack mt={2} spacing={2}>
            <Text fontSize="xs" color="gray.500">Last search URL:</Text>
            <Code fontSize="xs" colorScheme="gray">{debugUrl}</Code>
            <Badge colorScheme="purple" variant="subtle">{apiBase.replace(/^https?:\/\//, '')}</Badge>
          </HStack>
        )}

        {openapiTried.length > 0 && (
          <Box mt={4} borderTopWidth="1px" pt={4}>
            <Text fontSize="sm" color="gray.500" mb={2}>
              Tried fetching OpenAPI from:
            </Text>
            <VStack align="start" spacing={1} maxH="140px" overflowY="auto">
              {openapiTried.map((u) => (
                <HStack key={u} spacing={2}>
                  <LinkIcon color="gray.400" />
                  <Code fontSize="xs">{u}</Code>
                </HStack>
              ))}
            </VStack>
            {openapiError && (
              <Text fontSize="sm" color="red.500" mt={2}>{openapiError}</Text>
            )}
          </Box>
        )}

        {foundDocs && discovered.length > 0 && (
          <Box mt={4} borderTopWidth="1px" pt={4}>
            <Text fontWeight="semibold" mb={1}>Discovered API paths</Text>
            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={2} maxH="200px" overflowY="auto">
              {discovered.map((p) => (
                <Code key={p} fontSize="xs">{p}</Code>
              ))}
            </SimpleGrid>
          </Box>
        )}
      </Box>

      {/* Results Card */}
      <Box
        borderWidth="1px"
        bg="white"
        _dark={{ bg: 'gray.800' }}
        rounded="2xl"
        shadow="sm"
        overflow="hidden"
      >
        <HStack justify="space-between" px={{ base: 4, md: 6 }} py={4}>
          <HStack spacing={3}>
            <Heading size="md">Results</Heading>
            <Badge variant="subtle" colorScheme={rows.length ? 'green' : 'gray'}>
              {rows.length} found
            </Badge>
          </HStack>
          <Text fontSize="sm" color="gray.500">Board = published pay (not disclosed to carriers)</Text>
        </HStack>
        <Divider />

        {/* Table header */}
        <Box overflowX="auto">
          <Box as="table" w="100%" sx={{ borderCollapse: 'separate', borderSpacing: 0 }}>
            <Box as="thead" position="sticky" top={0} bg="white" _dark={{ bg: 'gray.800' }} zIndex={1}>
              <Box as="tr">
                {['Load ID', 'Lane', 'Pickup → Delivery', 'Equipment', 'Miles', 'Board', 'Notes'].map((h) => (
                  <Box
                    as="th"
                    key={h}
                    textAlign="left"
                    fontWeight="semibold"
                    fontSize="sm"
                    color="gray.600"
                    px={4}
                    py={3}
                    borderBottom="1px solid"
                    borderColor="gray.100"
                  >
                    {h}
                  </Box>
                ))}
              </Box>
            </Box>

            <Box as="tbody">
              {loading ? (
                [...Array(3)].map((_, i) => (
                  <Box as="tr" key={`sk-${i}`}>
                    <Box as="td" colSpan={7} px={4} py={3} borderBottom="1px solid" borderColor="gray.50">
                      <Skeleton height="20px" />
                    </Box>
                  </Box>
                ))
              ) : rows.length === 0 ? (
                <Box as="tr">
                  <Box as="td" colSpan={7} px={4} py={6} color="gray.500">
                    No results yet. Fill the form and press <Kbd>Search</Kbd>.
                  </Box>
                </Box>
              ) : (
                rows.map((r, idx) => (
                  <Box
                    as="tr"
                    key={r.load_id}
                    bg={idx % 2 ? 'gray.50' : 'white'}
                    _dark={{ bg: idx % 2 ? 'blackAlpha.300' : 'gray.800' }}
                    _hover={{ bg: 'blackAlpha.50', _dark: { bg: 'whiteAlpha.100' } }}
                    transition="background 120ms ease"
                  >
                    <Box as="td" px={4} py={3} borderBottom="1px solid" borderColor="gray.100">
                      <HStack spacing={2}>
                        <Badge>{r.load_id}</Badge>
                        {r.commodity_type && (
                          <Badge colorScheme="purple" variant="subtle">{r.commodity_type}</Badge>
                        )}
                      </HStack>
                    </Box>

                    <Box as="td" px={4} py={3} borderBottom="1px solid" borderColor="gray.100">
                      <Text noOfLines={1}>
                        {r.origin} <Text as="span" color="gray.400">→</Text> {r.destination}
                      </Text>
                    </Box>

                    <Box as="td" px={4} py={3} borderBottom="1px solid" borderColor="gray.100">
                      <VStack align="start" spacing={0.5}>
                        <Text fontSize="sm" noOfLines={1}>
                          {new Date(r.pickup_datetime).toLocaleString()}
                        </Text>
                        <Text fontSize="xs" color="gray.500" noOfLines={1}>
                          {new Date(r.delivery_datetime).toLocaleString()}
                        </Text>
                      </VStack>
                    </Box>

                    <Box as="td" px={4} py={3} borderBottom="1px solid" borderColor="gray.100">
                      <HStack spacing={2} wrap="wrap">
                        <Badge colorScheme={badgeForEq(r.equipment_type)}>{r.equipment_type}</Badge>
                        {r.dimensions && <Badge variant="outline">{r.dimensions}</Badge>}
                        {r.weight ? <Badge variant="outline">{Math.round(r.weight)} lb</Badge> : null}
                        {r.num_of_pieces ? <Badge variant="outline">{r.num_of_pieces} pcs</Badge> : null}
                      </HStack>
                    </Box>

                    <Box as="td" px={4} py={3} borderBottom="1px solid" borderColor="gray.100">
                      {r.miles ?? '—'}
                    </Box>

                    <Box as="td" px={4} py={3} borderBottom="1px solid" borderColor="gray.100">
                      <Badge colorScheme="green" variant="subtle">{fmtUSD(r.loadboard_rate)}</Badge>
                    </Box>

                    <Box as="td" px={4} py={3} borderBottom="1px solid" borderColor="gray.100" maxW="320px">
                      <Text noOfLines={2}>{r.notes ?? '—'}</Text>
                    </Box>
                  </Box>
                ))
              )}
            </Box>
          </Box>
        </Box>
      </Box>
    </Box>
  );
}

// small helper for equipment badge color
function badgeForEq(eq?: string) {
  if (!eq) return 'gray';
  const s = eq.toLowerCase();
  if (s.includes('reefer')) return 'blue';
  if (s.includes('flatbed')) return 'orange';
  if (s.includes('step')) return 'purple';
  if (s.includes('tanker')) return 'pink';
  return 'teal';
}
