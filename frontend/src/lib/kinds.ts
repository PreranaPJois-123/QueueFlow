import { BedDouble, Scissors, Stethoscope, type LucideIcon } from "lucide-react";
import type { VenueKind } from "../types";

export const kindMeta: Record<VenueKind, {
  label: string; plural: string; path: string; tint: string; text: string; solid: string; icon: LucideIcon;
}> = {
  HOSPITAL: { label: "Hospital", plural: "Hospitals", path: "/hospitals", tint: "bg-care-50", text: "text-care-600", solid: "#0f7a6e", icon: Stethoscope },
  SHOP: { label: "Shop", plural: "Shops", path: "/shops", tint: "bg-shop-50", text: "text-shop-600", solid: "#8e3b6f", icon: Scissors },
  HOTEL: { label: "Hotel", plural: "Hotels", path: "/hotels", tint: "bg-stay-50", text: "text-stay-600", solid: "#3b4cca", icon: BedDouble },
};
