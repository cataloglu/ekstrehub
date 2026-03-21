import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

/** Home Assistant Ingress: Vite strips raw inline scripts from index.html; inject at build time. */
function ingressBasePlugin(): Plugin {
  const snippet = `    <script>
      (function () {
        function ingressBasePath() {
          var path = location.pathname || "/";
          var parts = path.split("/").filter(Boolean);
          if (parts.length >= 3 && parts[0] === "api" && parts[1] === "hassio_ingress") {
            return "/" + parts.slice(0, 3).join("/") + "/";
          }
          if (parts.length >= 2 && parts[0] === "app") {
            return "/" + parts.slice(0, 2).join("/") + "/";
          }
          if (parts.length >= 3 && parts[0] === "hassio" && parts[1] === "ingress") {
            return "/" + parts.slice(0, 3).join("/") + "/";
          }
          if (path !== "/" && !path.endsWith("/")) return path + "/";
          return path === "" ? "/" : path;
        }
        var b = document.createElement("base");
        b.href = ingressBasePath();
        document.head.insertBefore(b, document.head.firstChild);
      })();
    </script>
`;
  return {
    name: "ingress-base-href",
    transformIndexHtml(html) {
      return html.replace("<head>", `<head>\n${snippet}`);
    }
  };
}

export default defineConfig({
  base: "./",
  plugins: [ingressBasePlugin(), react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true
      }
    }
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    globals: true
  }
});
