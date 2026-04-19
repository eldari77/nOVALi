import adapter from "@sveltejs/adapter-static";
import { vitePreprocess } from "@sveltejs/vite-plugin-svelte";

const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      pages: "build",
      assets: "build",
      fallback: null,
      precompress: false,
      strict: false,
    }),
    paths: {
      base: "/shell",
    },
    prerender: {
      handleHttpError: "warn",
      crawl: false,
      entries: ["*"],
    },
    appDir: "app",
  },
};

export default config;
