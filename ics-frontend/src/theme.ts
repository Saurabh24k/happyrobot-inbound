// src/theme.ts
import { extendTheme, type ThemeConfig } from "@chakra-ui/react";

const config: ThemeConfig = {
  initialColorMode: "system",
  useSystemColorMode: true,
};

const theme = extendTheme({
  config,
  fonts: {
    heading:
      'Poppins, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji"',
    body:
      'Poppins, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji"',
  },
  colors: {
    brand: {
      50:  "#e7f1ff",
      100: "#c2d7ff",
      200: "#9bbcff",
      300: "#73a1ff",
      400: "#4d88ff",
      500: "#336ee6",
      600: "#2756b4",
      700: "#1c3e82",
      800: "#102650",
      900: "#061329",
    },
  },
  styles: {
    global: {
      "html, body, #root": { height: "100%" },
      body: {
        bg: "gray.50",
        color: "gray.800",
        _dark: { bg: "gray.900", color: "gray.100" },
      },
    },
  },
  radii: {
    xl: "14px",
    "2xl": "18px",
  },
  components: {
    Button: {
      baseStyle: { rounded: "2xl" },
      defaultProps: { colorScheme: "brand" },
    },
    Badge: {
      baseStyle: { rounded: "full" },
    },
    Tag: {
      baseStyle: { rounded: "full" },
    },
    Card: {
      baseStyle: { rounded: "2xl" },
    },
  },
});

export default theme;
