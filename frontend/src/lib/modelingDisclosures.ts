/**
 * Per-asset "what is and isn't modeled" disclosures.
 *
 * Keyed by a disclosure key (account type today; legacy asset classes such as
 * "insurance", "annuity", "private", "realestate" are added by their phases).
 * Rendered by <ModelingDisclosure> at the point of entry so every asset carries
 * its own honest caveats, consistent with the modeled / estimated / assumed
 * provenance taxonomy used across the app.
 */

export interface ModelingSpec {
  /** Short statutory/behavioral facts the engine DOES model. */
  modeled: string[];
  /** Things deliberately NOT modeled (the honest caveats). */
  notModeled: string[];
}

export const MODELING_DISCLOSURES: Record<string, ModelingSpec> = {
  tax_deferred: {
    modeled: [
      "Withdrawals taxed as ordinary income",
      "Required minimum distributions (SECURE 2.0 ages 73/75)",
      "Heirs owe ordinary income tax on the inherited balance (IRD, IRC §691)",
    ],
    notModeled: ["The 10-year inherited-IRA drawdown for non-spouse heirs"],
  },
  roth: {
    modeled: [
      "Tax-free qualified withdrawals",
      "No RMDs during the owner's life",
      "Passes income-tax-free to heirs",
    ],
    notModeled: [
      "Per-layer contribution/conversion/earnings ordering before age 59½ (treated as basis)",
    ],
  },
  taxable: {
    modeled: [
      "Annual qualified-dividend drag and cost-basis tracking",
      "Pro-rata capital-gain realization on withdrawal (0/15/20% stacking)",
      "Basis step-up at death (IRC §1014)",
    ],
    notModeled: ["Specific-lot selection or tax-loss harvesting"],
  },
  hsa: {
    modeled: [
      "Tax-free for qualified medical costs (pays Medicare Part B first)",
      "Heirs owe ordinary income tax on the inherited balance (IRD)",
    ],
    notModeled: ["20% non-medical penalty before age 65 beyond the modeled drawdown order"],
  },
  cash: {
    modeled: ["Interest taxed annually as ordinary income", "Basis step-up at death"],
    notModeled: ["Distinct money-market vs. savings yields"],
  },
};

export function modelingSpec(key: string): ModelingSpec | undefined {
  return MODELING_DISCLOSURES[key];
}
