// src/theme.ts
import { extendTheme, type ThemeConfig } from "@chakra-ui/react";

const config: ThemeConfig = {
  initialColorMode: "system",
  useSystemColorMode: true,
};

const theme = extendTheme({
  config,
  colors: {
    brand: {
      50: "#e7f1ff",
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
      body: {
        bg: "gray.50",
        _dark: { bg: "gray.900" },
      },
    },
  },
});

export default theme;
