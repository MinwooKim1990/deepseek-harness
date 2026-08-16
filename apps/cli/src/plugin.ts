/** External profile package installation is deliberately absent from the hardened build. */
export function runPlugin(profile: string, args: readonly string[]): number {
  void profile
  void args
  process.stderr.write('dsh: external profile plugin management is disabled in this hardened build\n')
  return 126
}
