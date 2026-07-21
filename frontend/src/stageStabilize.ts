import type { ChannelParams } from './api'

/** Consecutive idle polls before accepting Leerlauf (hides 1-tick stage glitches). */
export const IDLE_STAGE_CONFIRM = 2

export type StageStabilizeState = {
  idleStreak: Map<number, number>
  lastRunning: Map<number, ChannelParams>
}

export function createStageStabilizeState(): StageStabilizeState {
  return { idleStreak: new Map(), lastRunning: new Map() }
}

function isIdleChannel(c: ChannelParams): boolean {
  return Boolean(c.idle) || c.stage_name === 'Leerlauf'
}

/**
 * Hold the last non-idle stage when the device briefly reports Leerlauf.
 * Confirmed idle (IDLE_STAGE_CONFIRM polls) clears the hold.
 */
export function stabilizeChannels(
  state: StageStabilizeState,
  incoming: ChannelParams[],
): ChannelParams[] {
  return incoming.map((ch, idx) => {
    // List index — same remapping as liveSeries (wire channel byte can be wrong).
    const channel = idx
    const idle = isIdleChannel(ch)

    if (!idle) {
      state.idleStreak.set(channel, 0)
      state.lastRunning.set(channel, ch)
      return ch
    }

    const streak = (state.idleStreak.get(channel) ?? 0) + 1
    state.idleStreak.set(channel, streak)
    const prev = state.lastRunning.get(channel)
    if (prev && streak < IDLE_STAGE_CONFIRM) {
      return {
        ...ch,
        stage: prev.stage,
        stage_name: prev.stage_name,
        idle: false,
      }
    }

    state.lastRunning.delete(channel)
    return ch
  })
}
