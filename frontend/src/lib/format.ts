export const activeStatus = (status: string) =>
  ["WAITING", "CALLED", "SERVING"].includes(status);
export const dateTime = (value: string) =>
  new Date(
    value.endsWith("Z") || /[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`,
  ).toLocaleString();
export const predictionLabel = (source: string) =>
  source === "ml_knn"
    ? "ML estimate · historical nearest neighbours"
    : source === "calculated_history"
      ? "Calculated from recent service history"
      : "Calculated · configured service duration";
