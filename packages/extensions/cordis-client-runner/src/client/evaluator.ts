/** Fail-closed browser-half API retained for type compatibility. */
import type { CordisDynamicPluginId } from '@deepseek-ai/dsh-api-remotes/client'

export interface DynamicCordisEvaluatedPlugin {
  name?: string
  inject?: string[]
  apply: (ctx: unknown, config?: unknown) => unknown
}

export interface DynamicCordisClosureEnv {
  invoke(method: string, args: unknown): Promise<unknown>
  noteError(message: string): void
}

export const DYNAMIC_CLIENT_REDIRECTS: Readonly<Record<string, string>> = {
  setTimeout: 'dynamic packages are disabled in this hardened build',
  setInterval: 'dynamic packages are disabled in this hardened build',
  clearTimeout: 'dynamic packages are disabled in this hardened build',
  clearInterval: 'dynamic packages are disabled in this hardened build',
  fetch: 'dynamic packages are disabled in this hardened build',
  require: 'dynamic packages are disabled in this hardened build',
}

export class DynamicCordisStyles {
  private readonly tags = new Set<HTMLStyleElement>()
  constructor(private readonly pluginId: CordisDynamicPluginId) {}
  insert(css: string): () => void {
    if (typeof css !== 'string') throw new Error('styles.insert(css) needs a CSS string')
    const tag = document.createElement('style')
    tag.dataset.dyn = this.pluginId
    tag.textContent = css
    document.head.append(tag)
    this.tags.add(tag)
    return () => { this.tags.delete(tag); tag.remove() }
  }
  get count(): number { return this.tags.size }
  dispose(): void { for (const tag of this.tags) tag.remove(); this.tags.clear() }
}

export function isDynamicCordisPlugin(value: unknown): value is DynamicCordisEvaluatedPlugin | ((ctx: unknown) => unknown) {
  if (typeof value === 'function') return true
  return typeof value === 'object' && value !== null
    && typeof (value as { apply?: unknown }).apply === 'function'
}

export async function evaluateClientHalf(
  pluginId: CordisDynamicPluginId,
  clientCode: string,
  env: DynamicCordisClosureEnv,
  styles: DynamicCordisStyles,
): Promise<DynamicCordisEvaluatedPlugin | ((ctx: unknown) => unknown)> {
  void pluginId
  void clientCode
  void env
  void styles
  throw new Error('dynamic Cordis packages are disabled in this hardened build')
}
