import { Box, Text } from '@chakra-ui/react';
import { NavLink, Outlet } from 'react-router-dom';
import type { ReactNode } from 'react';

export default function Layout() {
  return (
    <Box minH="100vh" display="grid" gridTemplateColumns="240px 1fr">
      {/* Left nav */}
      <Box as="nav" borderRightWidth="1px" p={4}>
        <Text fontWeight="bold" mb={4}>
          Acme Logistics – Inbound Carrier Sales
        </Text>
        <Box display="grid" gap={2}>
          <NavItem to="/">Dashboard</NavItem>
          <NavItem to="/calls">Calls</NavItem>
          <NavItem to="/loads">Loads</NavItem>
          <NavItem to="/settings">Settings</NavItem>
        </Box>
      </Box>

      {/* Main content */}
      <Box as="main" p={4}>
        <Outlet />
      </Box>
    </Box>
  );
}

function NavItem({ to, children }: { to: string; children: ReactNode }) {
  return (
    <NavLink
      to={to}
      style={({ isActive }) => ({
        display: 'block',
        padding: '8px 10px',
        borderRadius: 8,
        textDecoration: 'none',
        color: isActive ? '#111827' : '#334155',
        background: isActive ? '#E2E8F0' : 'transparent',
      })}
    >
      {children}
    </NavLink>
  );
}
