<script lang="ts">
    import { server } from "@lib/server";
    import type { VulnerabilityDetails } from "@lib/types";
    import Hint from "svelte-hint";

    export let cveId: string;

    const cves = server.model?.vulnerabilities!;
    const vuln = cves.find((vuln) => vuln.id === cveId)!;

    const href = `https://nvd.nist.gov/vuln/detail/${vuln.id}`;
    const { likelihood, impact } = getMetrics(vuln);

    function getMetrics(vuln: VulnerabilityDetails) {
        if (vuln.metrics.cvssMetricV2) {
            const metricV2 = vuln.metrics.cvssMetricV2[0];
            return {
                score: metricV2.cvssData.baseScore,
                likelihood: metricV2.exploitabilityScore,
                impact: metricV2.impactScore,
            };
        } else if (vuln.metrics.cvssMetricV31) {
            const metricV31 = vuln.metrics.cvssMetricV31[0];
            return {
                score: metricV31.cvssData.baseScore,
                likelihood: metricV31.exploitabilityScore,
                impact: metricV31.impactScore,
            };
        } else {
            return {
                score: null,
                likelihood: null,
                impact: null,
            };
        }
    }

    function getScoreRange(score: number | null) {
        if (score === null) {
            return "unknown";
        }

        if (score > 8.9) {
            return "critical";
        }
        if (score < 3.9) {
            return "low";
        } else if (score < 7.9) {
            return "medium";
        } else {
            return "high";
        }
    }
</script>

<div class="cve">
    <div class="id">
        <b>{vuln.id}</b>
        <Hint text="Open vulnerability in NIST NVD.">
            <a {href} target="_blank"> NIST NVD </a>
        </Hint>
    </div>
    <div>
        <div class="score score_{getScoreRange(likelihood)}">
            Likelihood=<b>{likelihood}</b>
        </div>
        <div class="score score_{getScoreRange(impact)}">
            Impact=<b>{impact}</b>
        </div>
    </div>
    <div>
        <div class="score score_{vuln.score[2].toLowerCase()}">
            <b>{vuln.score[1]}</b>
            {vuln.score[2]}

            <span class="monospace">
                {vuln.v2vector ?? ""}
            </span>
        </div>
    </div>
</div>

<style lang="scss">
    .cve {
        display: grid;
        grid-template-rows: auto auto auto;
        gap: 1px;
    }

    .id {
        a {
            color: rgba(0, 0, 0, 0.6);
            text-decoration: none;

            &:hover {
                background: black;
                color: white;
            }
        }
    }

    .score {
        display: inline-block;
        padding: 0.125rem 0.25rem;
        border-radius: 4px;

        &.score_low {
            background: #4caf50;
        }
        &.score_medium {
            background: #ffeb3b;
        }
        &.score_high {
            background: #ff9800;
        }
        &.score_critical {
            background: #f44336;
            color: white;
        }
    }

    .monospace {
        font-family: monospace;
        font-weight: bold;
    }
</style>
