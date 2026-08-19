module.exports = [
  {
    ignores: ['node_modules/**', 'reports/**', 'test-results/**', '.auth/**', '.tools/**'],
  },
  {
    files: ['**/*.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'commonjs',
      globals: {
        Buffer: 'readonly', console: 'readonly', process: 'readonly', __dirname: 'readonly',
        module: 'readonly', require: 'readonly', URL: 'readonly', setTimeout: 'readonly',
        document: 'readonly', sessionStorage: 'readonly',
      },
    },
    rules: {
      'no-undef': 'error',
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
      'no-empty': 'error',
      'no-unreachable': 'error',
    },
  },
];
