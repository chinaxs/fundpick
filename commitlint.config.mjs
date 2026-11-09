export default {
  extends: ['@commitlint/config-conventional'],
  rules: {
    // 中文项目放宽 subject 长度限制
    'header-max-length': [2, 'always', 120],
    'subject-case': [0],
    'type-enum': [
      2,
      'always',
      ['feat', 'fix', 'docs', 'style', 'refactor', 'perf', 'test', 'build', 'ci', 'chore', 'revert'],
    ],
  },
}
