// src/pages/Calls.tsx
import { useMemo, useState } from 'react';
import {
  Box,
  Heading,
  HStack,
  VStack,
  Text,
  Input,
  Button,
  ButtonGroup,
  IconButton,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Badge,
  Tooltip,
  Spinner,
  Divider,
} from '@chakra-ui/react';
import { format } from 'date-fns';
import { Link } from 'react-router-dom';
import { RepeatIcon } from '@chakra-ui/icons';
import { useCalls } from '../api/hooks';

function lastNDays(n: number): { since: string; until: string } {
  const now = new Date();
  const until = format(now, 'yyyy-MM-dd');
  const sinceDate = new Date(now.getTime() - (n - 1) * 24 * 60 * 60 * 1000);
  const since = format(sinceDate, 'yyyy-MM-dd');
  return { since, until };
}
function monthToDate(): { since: string; until: string } {
  const now = new Date();
  const since = format(new Date(now.getFullYear(), now.getMonth(), 1), 'yyyy-MM-dd');
  const until = format(now, 'yyyy-MM-dd');
  return { since, until };
}

function outcomeColor(outcome?: string) {
  switch ((outcome || '').toLowerCase()) {
    case 'booked':
      return 'green';
    case 'no-agreement':
      return 'orange';
    case 'no-match':
      return 'gray';
    case 'failed-auth':
      return 'red';
    case 'abandoned':
      return 'purple';
    default:
      return 'gray';
  }
}
function sentimentColor(s?: string) {
  switch ((s || '').toLowerCase()) {
    case 'positive':
      return 'green';
    case 'neutral':
      return 'gray';
    case 'negative':
      return 'red';
    default:
      return 'gray';
  }
}

export default function Calls() {
  // date range
  const initial = useMemo(() => lastNDays(7), []);
  const [since, setSince] = useState(initial.since);
  const [until, setUntil] = useState(initial.until);

  // data
  const { data, isLoading, error, refetch, isFetching } = useCalls(since, until, 50, 0);
  const rows = data?.items ?? [];

  const applyRange = (range: '7' | '30' | 'mtd') => {
    const r = range === 'mtd' ? monthToDate() : lastNDays(range === '7' ? 7 : 30);
    setSince(r.since);
    setUntil(r.until);
    setTimeout(() => refetch(), 0);
  };

  return (
    <VStack align="stretch" gap={6}>
      {/* Header row */}
      <HStack justify="space-between" align="center">
        <Heading size="lg">Calls</Heading>
        <HStack gap={2}>
          <Tooltip content="Refresh">
            <IconButton aria-label="Refresh" size="sm" onClick={() => refetch()} disabled={isFetching}>
              {isFetching ? <Spinner size="sm" /> : <RepeatIcon />}
            </IconButton>
          </Tooltip>
        </HStack>
      </HStack>

      {/* Range controls */}
      <Box borderWidth="1px" rounded="lg" p={4} bg={{ base: 'white', _dark: 'gray.950' }}>
        <HStack gap={4} wrap="wrap" align="center">
          <HStack gap={2}>
            <Text fontSize="sm" color="gray.500">Since</Text>
            <Input
              type="date"
              value={since}
              onChange={(e) => setSince(e.target.value)}
              onBlur={() => refetch()}
              size="sm"
              maxW="180px"
            />
          </HStack>
          <HStack gap={2}>
            <Text fontSize="sm" color="gray.500">Until</Text>
            <Input
              type="date"
              value={until}
              onChange={(e) => setUntil(e.target.value)}
              onBlur={() => refetch()}
              size="sm"
              maxW="180px"
            />
          </HStack>

          <Divider orientation="vertical" />

          <ButtonGroup size="sm" isAttached>
            <Button onClick={() => applyRange('7')}>Last 7</Button>
            <Button onClick={() => applyRange('30')}>Last 30</Button>
            <Button onClick={() => applyRange('mtd')}>MTD</Button>
          </ButtonGroup>

          <Text fontSize="sm" color="gray.500" ml="auto">
            {isLoading || isFetching ? 'Loading…' : ' '}
          </Text>
        </HStack>
      </Box>

      {/* Error */}
      {error && (
        <Box borderWidth="1px" borderColor="red.300" bg="red.50" _dark={{ bg: 'red.900', borderColor: 'red.700' }} rounded="lg" p={4}>
          <Text><b>Oops.</b> Couldn’t load calls. Try again.</Text>
        </Box>
      )}

      {/* Table */}
      <TableContainer borderWidth="1px" rounded="lg" bg={{ base: 'white', _dark: 'gray.950' }}>
        <Table size="sm">
          <Thead bg={{ base: 'gray.50', _dark: 'gray.900' }}>
            <Tr>
              <Th>Started</Th>
              <Th>MC</Th>
              <Th>Load</Th>
              <Th>Outcome</Th>
              <Th>Rounds</Th>
              <Th isNumeric>Agreed</Th>
              <Th>Sentiment</Th>
            </Tr>
          </Thead>
          <Tbody>
            {rows.length === 0 ? (
              <Tr>
                <Td colSpan={7} color="gray.500">
                  No calls in this range.
                </Td>
              </Tr>
            ) : (
              rows.map((r: any) => (
                <Tr key={r.id} _hover={{ bg: { base: 'gray.50', _dark: 'gray.900' } }}>
                  <Td>
                    <Link to={`/calls/${encodeURIComponent(r.id)}`}>
                      <Text as="span" color="blue.500">{r.started_at}</Text>
                    </Link>
                  </Td>
                  <Td>{r.mc_number ?? '—'}</Td>
                  <Td>{r.selected_load_id ?? '—'}</Td>
                  <Td>
                    <Badge variant="subtle" colorScheme={outcomeColor(r.outcome)}>
                      {r.outcome ?? '—'}
                    </Badge>
                  </Td>
                  <Td>{r.negotiation_round ?? '—'}</Td>
                  <Td isNumeric>{r.agreed_rate != null ? `$${r.agreed_rate}` : '—'}</Td>
                  <Td>
                    <Badge variant="subtle" colorScheme={sentimentColor(r.sentiment)}>
                      {r.sentiment ?? '—'}
                    </Badge>
                  </Td>
                </Tr>
              ))
            )}
          </Tbody>
        </Table>
      </TableContainer>
    </VStack>
  );
}
