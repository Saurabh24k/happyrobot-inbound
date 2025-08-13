// src/main.tsx
import React from "react";
import ReactDOM from "react-dom/client";

import {
  ChakraProvider,
  Box,
  Container,
  HStack,
  Heading,
  Spacer,
  IconButton,
  Tooltip,
  useColorMode,
  useColorModeValue,
} from "@chakra-ui/react";
import { SunIcon, MoonIcon } from "@chakra-ui/icons";

import { BrowserRouter, Routes, Route, Navigate, NavLink } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import theme from "./theme";

// Pages
import Dashboard from "./pages/Dashboard";
import Calls from "./pages/Calls";
import CallDetail from "./pages/CallDetail";
import Loads from "./pages/Loads";
import Settings from "./pages/Settings";

const queryClient = new QueryClient();

function ColorModeToggle() {
  const { colorMode, toggleColorMode } = useColorMode();
  const isDark = colorMode === "dark";
  return (
    <Tooltip label={isDark ? "Switch to light" : "Switch to dark"}>
      <IconButton
        aria-label="Toggle color mode"
        size="sm"
        variant="ghost"
        onClick={toggleColorMode}
        icon={isDark ? <SunIcon /> : <MoonIcon />}
      />
    </Tooltip>
  );
}

function NavItem({ to, children }: { to: string; children: React.ReactNode }) {
  const hoverBg = useColorModeValue("gray.100", "gray.800");
  const activeBg = useColorModeValue("gray.200", "gray.700");
  return (
    <NavLink to={to} end>
      {({ isActive }) => (
        <Box
          as="span"
          px="3"
          py="2"
          rounded="md"
          fontWeight={isActive ? 700 : 500}
          bg={isActive ? activeBg : "transparent"}
          _hover={{ bg: hoverBg }}
          cursor="pointer"
          userSelect="none"
        >
          {children}
        </Box>
      )}
    </NavLink>
  );
}

function Layout({ children }: { children: React.ReactNode }) {
  const bodyBg = useColorModeValue("gray.50", "gray.900");
  const topBg = useColorModeValue("white", "gray.900");
  const borderColor = useColorModeValue("blackAlpha.200", "whiteAlpha.300");

  return (
    <Box minH="100dvh" bg={bodyBg}>
      {/* Top bar */}
      <Box borderBottomWidth="1px" borderColor={borderColor} bg={topBg} position="sticky" top={0} zIndex={10}>
        <Container maxW="6xl" py={3}>
          <HStack spacing={4}>
            <Heading size="md">Acme Carrier Sales</Heading>
            <Spacer />
            <HStack spacing={1}>
              <NavItem to="/dashboard">Dashboard</NavItem>
              <NavItem to="/calls">Calls</NavItem>
              <NavItem to="/loads">Loads</NavItem>
              <NavItem to="/settings">Settings</NavItem>
              <ColorModeToggle />
            </HStack>
          </HStack>
        </Container>
      </Box>

      {/* Content */}
      <Container maxW="6xl" py={6}>
        {children}
      </Container>
    </Box>
  );
}

function AppTree() {
  return (
    <React.StrictMode>
      <ChakraProvider theme={theme}>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <Layout>
              <Routes>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/calls" element={<Calls />} />
                <Route path="/calls/:id" element={<CallDetail />} />
                <Route path="/loads" element={<Loads />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Routes>
            </Layout>
          </BrowserRouter>
        </QueryClientProvider>
      </ChakraProvider>
    </React.StrictMode>
  );
}

function mount() {
  let el = document.getElementById("root");
  if (!el) {
    console.error("Root element #root not found. Creating it dynamically.");
    el = document.createElement("div");
    el.id = "root";
    document.body.appendChild(el);
  }
  ReactDOM.createRoot(el).render(<AppTree />);
}

// Ensure DOM exists before mounting (prevents React error 299)
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", mount, { once: true });
} else {
  mount();
}
