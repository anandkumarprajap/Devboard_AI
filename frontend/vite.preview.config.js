// Used only when serving the built app with `vite preview` inside the Docker
// image. It forwards /api to the backend — the same job nginx would do.
export default {
  preview: {
    proxy: {
      // AI calls go to the ai-service. Listed BEFORE /api (object order matters)
      // so /api/ai/* isn't swallowed by the /api rule.
      '/api/ai': {
        target: 'http://ai-service:3005',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/ai/, ''),
      },
      '/api': {
        target: 'http://backend:8080',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
};
