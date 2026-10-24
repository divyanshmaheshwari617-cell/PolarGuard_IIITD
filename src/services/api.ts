const API_BASE_URL = "http://127.0.0.1:8000";

export type ProviderStatus = {
  name: string;
  status: string;
  latest_observation?: string | null;
  provider_lag_days?: number | null;
  valid_cells?: number | null;
  iceberg_count?: number | null;
};

export type CommandCenterResponse = {
  ok: boolean;
  system: string;
  mode: string;

  providers: {
    sea_ice: ProviderStatus;
    icebergs: ProviderStatus;
    wind: ProviderStatus;
    ocean: ProviderStatus;
  };

  summary: {
    sea_ice_forecast_horizon_hours: number;
    safe_navigation: string;
  };

  timestamp_utc: string;
};

export async function getCommandCenter(): Promise<CommandCenterResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/command-center`
  );

  if (!response.ok) {
    throw new Error(
      `Command Center API failed: ${response.status}`
    );
  }

  return response.json();
}