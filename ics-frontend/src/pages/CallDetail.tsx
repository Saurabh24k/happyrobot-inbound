// src/pages/CallDetail.tsx
import { useParams, Link } from 'react-router-dom';
import { Box, Heading, Text } from '@chakra-ui/react';
import { useCallDetail } from '../api/hooks';

export default function CallDetail() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, error } = useCallDetail(id);

  return (
    <Box p={8} maxW="900px" mx="auto" display="grid" gap={8}>
      <Heading size="lg">Call Detail</Heading>
      <Text fontSize="sm"><Link to="/calls">← Back to Calls</Link></Text>

      {isLoading && <Text>Loading…</Text>}
      {error && <Text color="red.600">Error loading call.</Text>}
      {!data ? null : (
        <Box display="grid" gap={6}>
          <Box borderWidth="1px" borderRadius="lg" p={4} display="grid" gap={2}>
            <Text><b>Session:</b> {data.id}</Text>
            <Text><b>Started:</b> {data.started_at}</Text>
            <Text><b>MC:</b> {data.mc_number ?? '-'}</Text>
            <Text><b>Load:</b> {data.selected_load_id ?? '-'}</Text>
            <Text><b>Outcome:</b> {data.outcome ?? '-'}</Text>
            <Text><b>Sentiment:</b> {data.sentiment ?? '-'}</Text>
            <Text><b>Agreed rate:</b> {/* not in detail payload; shown on list */}</Text>
          </Box>

          <Box>
            <Heading size="md" mb={2}>Offer Timeline</Heading>
            {data.offers?.length ? (
              <Box display="flex" gap={2} flexWrap="wrap">
                {data.offers.map((o, idx) => (
                  <Box key={idx} borderWidth="1px" borderRadius="md" px={3} py={1} fontSize="sm">
                    {o.who}: ${o.value} <span style={{ color: '#64748b' }}>({o.t})</span>
                  </Box>
                ))}
              </Box>
            ) : (
              <Text color="gray.500">No offers recorded.</Text>
            )}
          </Box>

          <Box>
            <Heading size="md" mb={2}>Transcript</Heading>
            {data.transcript?.length ? (
              <Box borderWidth="1px" borderRadius="md" p={3} maxH="280px" overflow="auto" fontSize="sm" display="grid" gap={2}>
                {data.transcript.map((t, i) => (
                  <Box key={i}>
                    <b>{t.role}:</b> {t.text}
                  </Box>
                ))}
              </Box>
            ) : (
              <Text color="gray.500">No transcript available.</Text>
            )}
          </Box>

          <Box>
            <Heading size="md" mb={2}>Tool Calls</Heading>
            {data.tool_calls?.length ? (
              <Box as="ul" pl={5} fontSize="sm">
                {data.tool_calls.map((tc, i) => (
                  <li key={i}>
                    <code>{tc.fn}</code> — {tc.ok ? 'ok' : 'error'}
                  </li>
                ))}
              </Box>
            ) : (
              <Text color="gray.500">No tool calls recorded.</Text>
            )}
          </Box>
        </Box>
      )}
    </Box>
  );
}
