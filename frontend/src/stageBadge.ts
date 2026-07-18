/** CSS modifier for channel stage badges (backend sends German stage_name). */
export function stageBadgeClass(stageName: string | undefined): string {
  switch (stageName) {
    case 'Leerlauf':
      return 'badge-idle'
    case 'Pause/Warten':
    case 'Erhaltungsladung':
    case 'Entladen beendet':
      return 'badge-wait'
    case 'Entladen':
    case 'Laden':
      return 'badge-active'
    case 'Notabschaltung':
      return 'badge-emergency'
    default:
      return 'badge-idle'
  }
}
