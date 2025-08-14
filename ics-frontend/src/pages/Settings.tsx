import { useMemo, useRef, useState } from 'react';
import {
  Box,
  Heading,
  Text,
  Input,
  InputGroup,
  InputRightElement,
  InputLeftAddon,
  Button,
  IconButton,
  HStack,
  VStack,
  SimpleGrid,
  Badge,
  Tooltip,
  Code,
  useToast,
  Divider,
  Kbd,
  Tag,
  TagLabel,
  TagLeftIcon,
  useColorModeValue,
} from '@chakra-ui/react';
import {
  ViewIcon,
  ViewOffIcon,
  CopyIcon,
  CheckCircleIcon,
  WarningIcon,
  InfoOutlineIcon,
  DownloadIcon,
  AttachmentIcon,
  RepeatIcon,
  ExternalLinkIcon,
  TriangleDownIcon,
  SmallCloseIcon,
  TimeIcon,
} from '@chakra-ui/icons';
import { api, getApiBase } from '../api/client';

const LS_API_BASE = 'apiBase';
const LS_API_KEY = 'apiKey';

type Status = 'ok' | 'fail' | 'idle' | 'loading';

type Diag = {
  auth: Status;
  health: Status;
  openapi: Status;
  openapiPaths: string[];
  tried: string[];
  lastError?: string;
};

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

function normalizeBase(input: string) {
  let s = (input || '').trim();
  if (!s) return s;
  if (!/^https?:\/\//i.test(s)) s = `https://${s}`;
  s = s.replace(/\/+$/, '');
  return s;
}

function isLikelyUrl(s: string) {
  try {
    const test = /^https?:\/\//i.test(s) ? s : `https://${s}`;
    new URL(test);
    return true;
  } catch {
    return false;
  }
}

function statusBadge(status: Status) {
  switch (status) {
    case 'ok':
      return <Badge colorScheme="green">OK</Badge>;
    case 'fail':
      return <Badge colorScheme="red">Error</Badge>;
    case 'loading':
      return <Badge colorScheme="purple">Running…</Badge>;
    default:
      return <Badge>Idle</Badge>;
  }
}

function Pill({
  label,
  status,
}: {
  label: string;
  status: Status;
}) {
  const map: Record<Status, { color: string; icon: any }> = {
    ok: { color: 'green', icon: CheckCircleIcon },
    fail: { color: 'red', icon: SmallCloseIcon },
    loading: { color: 'purple', icon: TimeIcon },
    idle: { color: 'gray', icon: InfoOutlineIcon },
  };
  const { color, icon } = map[status];
  return (
    <Tag size="sm" colorScheme={color} variant="subtle" rounded="full">
      <TagLeftIcon as={icon} />
      <TagLabel>{label}</TagLabel>
    </Tag>
  );
}

export default function Settings() {
  const toast = useToast();
  const fileRef = useRef<HTMLInputElement>(null);

  const envBase = import.meta.env.VITE_API_BASE_URL || '';
  const envKey = import.meta.env.VITE_API_KEY || '';

  const [apiBase, setApiBase] = useState(
    window.localStorage.getItem(LS_API_BASE) || envBase,
  );
  const [apiKey, setApiKey] = useState(
    window.localStorage.getItem(LS_API_KEY) || envKey,
  );
  const [showKey, setShowKey] = useState(false);
  const [status, setStatus] = useState<string>('');

  const [diag, setDiag] = useState<Diag>({
    auth: 'idle',
    health: 'idle',
    openapi: 'idle',
    openapiPaths: [],
    tried: [],
  });

  // -------- Derived states for the banner --------
  const _allOk = diag.auth === 'ok' && diag.health === 'ok' && diag.openapi === 'ok';
  const anyLoading = [diag.auth, diag.health, diag.openapi].some((s) => s === 'loading');
  const anyFail = [diag.auth, diag.health, diag.openapi].some((s) => s === 'fail');
  const bannerBg = useColorModeValue(
    _allOk ? 'green.50' : anyFail ? 'red.50' : anyLoading ? 'purple.50' : 'gray.50',
    _allOk ? 'green.900' : anyFail ? 'red.900' : anyLoading ? 'purple.900' : 'gray.700'
  );
  const bannerBorder = useColorModeValue(
    _allOk ? 'green.200' : anyFail ? 'red.200' : anyLoading ? 'purple.200' : 'gray.200',
    _allOk ? 'green.700' : anyFail ? 'red.700' : anyLoading ? 'purple.700' : 'gray.600'
  );
  const bannerIconColor = useColorModeValue(
    _allOk ? 'green.600' : anyFail ? 'red.600' : anyLoading ? 'purple.600' : 'gray.500',
    _allOk ? 'green.300' : anyFail ? 'red.300' : anyLoading ? 'purple.300' : 'gray.300'
  );

  const computedBase = useMemo(() => normalizeBase(apiBase), [apiBase]);
  const curl = useMemo(() => {
    const base = normalizeBase(apiBase || getApiBase());
    const key = (apiKey || '').trim();
    const path = '/verify_mc';
    const payload = JSON.stringify({ mc_number: '123456', mock: true });
    return `curl -X POST '${base}${path}' \\
  -H 'content-type: application/json' \\
  -H 'x-api-key: ${key || '<your-api-key>'}' \\
  -d '${payload}'`;
  }, [apiBase, apiKey]);

  // -------- Actions --------
  const save = () => {
    const base = normalizeBase(apiBase);
    if (base && !isLikelyUrl(base)) {
      toast({ status: 'warning', title: 'Base URL looks off', description: 'Double-check host and scheme.' });
    }
    window.localStorage.setItem(LS_API_BASE, base);
    window.localStorage.setItem(LS_API_KEY, (apiKey || '').trim());
    try {
      (api.defaults.headers as any)['x-api-key'] = (apiKey || '').trim();
    } catch { /* noop */ }
    setStatus('Saved ✓  Try “Run All Tests”.');
    toast({ status: 'success', title: 'Settings saved' });
  };

  const clearLocal = () => {
    window.localStorage.removeItem(LS_API_BASE);
    window.localStorage.removeItem(LS_API_KEY);
    setApiBase(envBase);
    setApiKey(envKey);
    setStatus('Reset to .env values.');
    toast({ status: 'info', title: 'Reset to .env defaults' });
  };

  const useDemo = () => {
    setApiBase('https://happyrobot-inbound.onrender.com');
    setApiKey('');
    setStatus('Demo preset applied. Save to persist.');
  };

  const useLocal = () => {
    setApiBase('http://localhost:8000');
    setStatus('Local preset applied. Save to persist.');
  };

  const copyKey = async () => {
    try {
      await navigator.clipboard.writeText(apiKey);
      toast({ status: 'success', title: 'API key copied' });
    } catch {
      toast({ status: 'error', title: 'Could not copy' });
    }
  };

  const copyCurl = async () => {
    try {
      await navigator.clipboard.writeText(curl);
      toast({ status: 'success', title: 'cURL copied' });
    } catch {
      toast({ status: 'error', title: 'Could not copy' });
    }
  };

  const exportConfig = () => {
    const cfg = {
      apiBase: normalizeBase(apiBase),
      apiKey: (apiKey || '').trim(),
      exportedAt: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(cfg, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'inbound-settings.json';
    a.click();
    URL.revokeObjectURL(url);
  };

  const importConfig = (file: File) => {
    const fr = new FileReader();
    fr.onload = () => {
      try {
        const json = JSON.parse(String(fr.result || '{}'));
        if (json.apiBase) setApiBase(json.apiBase);
        if (json.apiKey) setApiKey(json.apiKey);
        setStatus('Config loaded. Save to persist.');
        toast({ status: 'success', title: 'Config imported' });
      } catch (e: any) {
        toast({ status: 'error', title: 'Import failed', description: String(e?.message || e) });
      }
    };
    fr.readAsText(file);
  };

  // -------- Diagnostics --------
  const setDiagPatch = (patch: Partial<Diag>) =>
    setDiag((d) => ({ ...d, ...patch }));

  const testAuth = async () => {
    setDiagPatch({ auth: 'loading', lastError: undefined });
    setStatus('Testing authentication…');
    try {
      const { data } = await api.post('/verify_mc', { mc_number: '123456', mock: true });
      setDiagPatch({ auth: 'ok' });
      setStatus(`API OK • source=${data?.source ?? 'n/a'} • eligible=${String(data?.eligible)}`);
    } catch (e: any) {
      const msg =
        e?.response?.data?.detail ||
        e?.response?.status ||
        e?.message ||
        'Unknown error';
      setDiagPatch({ auth: 'fail', lastError: String(msg) });
      setStatus(`Auth error: ${String(msg)}`);
    }
  };

  const testHealth = async () => {
    setDiagPatch({ health: 'loading', lastError: undefined });
    setStatus('Pinging /health…');
    try {
      const res = await fetch(`${getApiBase()}/health`);
      if (res.ok) {
        setDiagPatch({ health: 'ok' });
        setStatus('Health OK');
      } else {
        setDiagPatch({ health: 'fail', lastError: String(res.status) });
        setStatus(`Health error: ${res.status}`);
      }
    } catch (e: any) {
      setDiagPatch({ health: 'fail', lastError: String(e?.message || e) });
      setStatus(`Health error: ${String(e?.message || e)}`);
    }
  };

  const testOpenapi = async () => {
    setDiagPatch({ openapi: 'loading', lastError: undefined, tried: [], openapiPaths: [] });
    const tried: string[] = [];
    try {
      for (const p of CANDIDATE_OPENAPI_PATHS) {
        const base = normalizeBase(getApiBase());
        const url = `${base}${p.startsWith('/') ? p : `/${p}`}`;
        tried.push(url);
        setDiag((d) => ({ ...d, tried: [...tried] }));

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
              setDiagPatch({ openapi: 'ok', openapiPaths: paths });
              setStatus(`Discovered ${paths.length} paths from ${p}.`);
              return;
            }
          } else {
            setDiagPatch({ openapi: 'ok', openapiPaths: [] });
            setStatus(`Found docs at ${p}. Open in a browser.`);
            return;
          }
        } catch {
          // try next
        }
      }
      setDiagPatch({ openapi: 'fail' });
      setStatus('Could not fetch OpenAPI/docs from any known path.');
    } catch (e: any) {
      setDiagPatch({ openapi: 'fail', lastError: String(e?.message || e) });
      setStatus(String(e?.message || e));
    }
  };

  const runAll = async () => {
    setStatus('Running all diagnostics…');
    save();
    await Promise.allSettled([testHealth(), testAuth(), testOpenapi()]);
    setStatus('Diagnostics complete.');
  };

  // -------- UI --------
  return (
    <Box maxW="900px" mx="auto" px={{ base: 4, md: 8 }} py={10} display="grid" gap={6}>
      {/* Connection Banner */}
      <Box
        borderWidth="1px"
        borderColor={bannerBorder}
        bg={bannerBg}
        rounded="2xl"
        p={{ base: 4, md: 5 }}
        display="flex"
        alignItems={{ base: 'start', md: 'center' }}
        justifyContent="space-between"
        gap={4}
        flexWrap="wrap"
      >
        <HStack spacing={3} align="center">
          <CheckCircleIcon color={bannerIconColor} boxSize={6} />
          <VStack align="start" spacing={0}>
            <Text fontWeight="semibold">
              {_allOk
                ? 'All connections healthy'
                : anyFail
                ? 'Checks failing — review below'
                : anyLoading
                ? 'Running diagnostics…'
                : 'Not tested yet'}
            </Text>
            <HStack spacing={2} mt={1} flexWrap="wrap">
              <Pill label="Auth" status={diag.auth} />
              <Pill label="Health" status={diag.health} />
              <Pill label="OpenAPI" status={diag.openapi} />
            </HStack>
          </VStack>
        </HStack>
        <HStack>
          <Button size="sm" variant="outline" onClick={runAll} leftIcon={<TriangleDownIcon />}>
            Run All Tests
          </Button>
        </HStack>
      </Box>

      {/* Header */}
      <HStack justify="space-between" align="start">
        <VStack align="start" spacing={1}>
          <Heading size="lg">Settings & Connections</Heading>
          <Text color="gray.500" fontSize="sm">
            Configure your API and verify connectivity. Values here override your frontend <Code>.env</Code> and persist in <Code>localStorage</Code>.
          </Text>
        </VStack>
        <HStack>
          <Tooltip label="Export config">
            <IconButton aria-label="Export" icon={<DownloadIcon />} variant="outline" onClick={exportConfig} />
          </Tooltip>
          <Tooltip label="Import config">
            <IconButton
              aria-label="Import"
              icon={<AttachmentIcon />}
              variant="outline"
              onClick={() => fileRef.current?.click()}
            />
          </Tooltip>
          <input
            ref={fileRef}
            type="file"
            accept="application/json"
            style={{ display: 'none' }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) importConfig(f);
              e.currentTarget.value = '';
            }}
          />
        </HStack>
      </HStack>

      {/* Config Card */}
      <Box borderWidth="1px" rounded="2xl" p={{ base: 4, md: 6 }} bg="white" _dark={{ bg: 'gray.800' }}>
        <SimpleGrid columns={{ base: 1, md: 2 }} spacing={5}>
          <Box>
            <Text fontSize="sm" mb={2}>API Base URL</Text>
            <InputGroup>
              <InputLeftAddon>URL</InputLeftAddon>
              <Input
                placeholder="https://happyrobot-inbound.onrender.com"
                value={apiBase}
                onChange={(e) => setApiBase(e.target.value)}
                isInvalid={!!apiBase && !isLikelyUrl(apiBase)}
              />
            </InputGroup>
            <HStack mt={2} spacing={2}>
              <Button size="sm" variant="outline" onClick={useDemo}>Use Demo</Button>
              <Button size="sm" variant="outline" onClick={useLocal}>Use Local</Button>
              <Button size="sm" variant="ghost" leftIcon={<RepeatIcon />} onClick={clearLocal}>
                Reset to .env
              </Button>
            </HStack>
          </Box>

          <Box>
            <Text fontSize="sm" mb={2}>API Key</Text>
            <InputGroup>
              <Input
                type={showKey ? 'text' : 'password'}
                placeholder="prod-xyz-123"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
              />
              <InputRightElement width="7.5rem">
                <HStack pr={2} spacing={1}>
                  <IconButton
                    aria-label="Copy key"
                    size="sm"
                    variant="ghost"
                    icon={<CopyIcon />}
                    onClick={copyKey}
                  />
                  <IconButton
                    aria-label={showKey ? 'Hide key' : 'Show key'}
                    size="sm"
                    variant="ghost"
                    icon={showKey ? <ViewOffIcon /> : <ViewIcon />}
                    onClick={() => setShowKey((s) => !s)}
                  />
                </HStack>
              </InputRightElement>
            </InputGroup>
            <Text fontSize="xs" color="gray.500" mt={2}>
              Header used: <Code>x-api-key</Code>
            </Text>
          </Box>
        </SimpleGrid>

        <HStack mt={4} spacing={3} wrap="wrap">
          <Button onClick={save} leftIcon={<CheckCircleIcon />}>Save</Button>
          <Button variant="outline" onClick={testAuth}>Test Auth</Button>
          <Button variant="outline" onClick={testHealth}>Health</Button>
          <Button variant="outline" onClick={testOpenapi}>OpenAPI</Button>
          <Button variant="ghost" onClick={runAll} leftIcon={<TriangleDownIcon />}>
            Run All Tests
          </Button>

          <HStack ml={{ base: 0, md: 'auto' }} spacing={2}>
            <Text fontSize="sm" color="gray.500">Sample cURL</Text>
            <Tooltip label="Copy cURL">
              <IconButton aria-label="Copy cURL" size="sm" variant="outline" icon={<CopyIcon />} onClick={copyCurl} />
            </Tooltip>
          </HStack>
        </HStack>

        <Box mt={2} p={3} bg="gray.50" _dark={{ bg: 'blackAlpha.300' }} rounded="md">
          <Code whiteSpace="pre-wrap" fontSize="xs">{curl}</Code>
        </Box>

        <HStack mt={3} spacing={2} align="center">
          <InfoOutlineIcon color="gray.400" />
          <Text fontSize="sm" color="gray.600">{status || 'Configure your connection and run diagnostics.'}</Text>
        </HStack>
      </Box>

      {/* Diagnostics Card */}
      <Box borderWidth="1px" rounded="2xl" p={{ base: 4, md: 6 }} bg="white" _dark={{ bg: 'gray.800' }}>
        <Heading size="sm" mb={3}>Diagnostics</Heading>
        <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
          <Box borderWidth="1px" rounded="lg" p={4}>
            <HStack justify="space-between">
              <Text fontWeight="semibold">Auth</Text>
              {statusBadge(diag.auth)}
            </HStack>
            <Text color="gray.500" fontSize="sm" mt={1}>
              POST <Code>/verify_mc</Code>
            </Text>
          </Box>

          <Box borderWidth="1px" rounded="lg" p={4}>
            <HStack justify="space-between">
              <Text fontWeight="semibold">Health</Text>
              {statusBadge(diag.health)}
            </HStack>
            <Text color="gray.500" fontSize="sm" mt={1}>
              GET <Code>/health</Code>
            </Text>
          </Box>

          <Box borderWidth="1px" rounded="lg" p={4}>
            <HStack justify="space-between">
              <Text fontWeight="semibold">OpenAPI</Text>
              {statusBadge(diag.openapi)}
            </HStack>
            <Text color="gray.500" fontSize="sm" mt={1}>
              Tries common docs paths
            </Text>
          </Box>
        </SimpleGrid>

        {diag.lastError && (
          <HStack mt={4} color="red.500">
            <WarningIcon />
            <Text fontSize="sm">Last error: {diag.lastError}</Text>
          </HStack>
        )}

        <Divider my={4} />

        <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
          <Box>
            <Text fontWeight="semibold" mb={2}>Base & headers</Text>
            <VStack align="start" spacing={1}>
              <HStack><Text w="140px" color="gray.500">Computed base</Text><Code>{computedBase || '(empty)'}</Code></HStack>
              <HStack><Text w="140px" color="gray.500">Env base</Text><Code>{envBase || '(empty)'}</Code></HStack>
              <HStack><Text w="140px" color="gray.500">Env key</Text><Code>{envKey ? '••••••••' : '(empty)'}</Code></HStack>
            </VStack>
          </Box>

          <Box>
            <Text fontWeight="semibold" mb={2}>OpenAPI discovery</Text>
            {diag.tried.length === 0 ? (
              <Text fontSize="sm" color="gray.500">Run the OpenAPI test to see attempted endpoints.</Text>
            ) : (
              <VStack align="start" spacing={1} maxH="160px" overflowY="auto">
                {diag.tried.map((u) => (
                  <HStack key={u} spacing={2}>
                    <ExternalLinkIcon color="gray.400" />
                    <Code fontSize="xs">{u}</Code>
                  </HStack>
                ))}
              </VStack>
            )}
          </Box>
        </SimpleGrid>

        {diag.openapiPaths.length > 0 && (
          <>
            <Divider my={4} />
            <Text fontWeight="semibold" mb={2}>Discovered API paths</Text>
            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={2} maxH="220px" overflowY="auto">
              {diag.openapiPaths.map((p) => (
                <Code key={p} fontSize="xs">{p}</Code>
              ))}
            </SimpleGrid>
          </>
        )}

        <Divider my={4} />
        <Text fontSize="xs" color="gray.500">
          Pro tip: press <Kbd>Save</Kbd> before running tests so the axios client and fetches use the latest
          <Code mx={1}>x-api-key</Code> and base URL.
        </Text>
      </Box>
    </Box>
  );
}
