/** 全站共用一次持仓代码查询；账号与请求版本检查阻止旧请求覆盖新状态。 */
export function useHoldingStatus() {
  const { user } = useAuth()
  const state = useState('portal:holding-status', () => ({
    owner: null as number | null,
    codes: [] as string[],
    loaded: false,
    loading: false,
    revision: 0,
  }))
  const codes = computed(
    () => new Set(state.value.owner === user.value?.id ? state.value.codes : []),
  )
  function isHeld(code: string) {
    return codes.value.has(code)
  }
  async function load(force = false) {
    const owner = user.value?.id ?? null
    if (state.value.owner !== owner) reset(owner)
    if (owner == null || (!force && (state.value.loaded || state.value.loading))) return
    const revision = ++state.value.revision
    state.value.loading = true
    try {
      const items = await getHeldFundCodes()
      if (user.value?.id === owner && state.value.revision === revision) {
        state.value.codes = items
        state.value.loaded = true
      }
    } catch {
      if (state.value.revision === revision) state.value.loaded = false
    } finally {
      if (state.value.revision === revision) state.value.loading = false
    }
  }
  function reset(owner: number | null = null) {
    state.value = {
      owner,
      codes: [],
      loaded: false,
      loading: false,
      revision: state.value.revision + 1,
    }
  }
  return { isHeld, load, reset }
}
