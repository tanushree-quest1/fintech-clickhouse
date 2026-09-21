const configuredApiBase = import.meta.env.VITE_API_BASE?.replace(/\/$/, '');

export const API_BASE = configuredApiBase || `${window.location.protocol}//${window.location.hostname}:8000`;

export const WS_URL = configuredApiBase
  ? configuredApiBase.replace(/^http/, 'ws') + '/ws/live'
  : `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.hostname}:8000/ws/live`;
