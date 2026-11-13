import { getInsightsSummary } from "../../api/insights";
import { useLoader } from "../../hooks/useLoader";

const loadInsights = () => getInsightsSummary();

// Shared by the Home insights and the Assistant "This Month" card. Loads once, reload() retries.
export function useInsightsSummary() {
  return useLoader(loadInsights);
}
