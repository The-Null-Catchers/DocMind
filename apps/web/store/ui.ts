import { create } from "zustand";
import type { Locale } from "@/lib/i18n";

type UIState = {
  locale: Locale;
  commandOpen: boolean;
  setLocale: (locale: Locale) => void;
  setCommandOpen: (open: boolean) => void;
};

export const useUI = create<UIState>((set) => ({
  locale: "en",
  commandOpen: false,
  setLocale: (locale) => set({ locale }),
  setCommandOpen: (commandOpen) => set({ commandOpen })
}));
