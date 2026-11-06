/**
 * Counts of a job's outcomes, from the memory the backend reports: each shot's bits as hex,
 * classical bit 0 least significant, as Qiskit prints them.
 */
import type { JobResult } from "@/lib/api/types";

/** How often each outcome came up in one circuit's shots, outcomes in order */
export interface CircuitCounts {
  name: string;
  counts: OutcomeCount[];
  shots: number;
}

export interface OutcomeCount {
  outcome: string;
  count: number;
}

/**
 * Gets the counts of each circuit of a result, or none if its memory is not counted, as at
 * measurement level 1, whose shots are IQ points
 *
 * @param result - the job's result
 * @returns the counts per circuit
 */
export function getCircuitCounts(result?: JobResult | null): CircuitCounts[] {
  if (!result?.circuits || result.meas_level === 1) {
    return [];
  }
  const memory = result.memory as string[][];
  return result.circuits.map((circuit, index) => {
    const shots = memory[index] ?? [];
    return {
      name: circuit.name,
      counts: countOutcomes(shots, circuit.num_clbits),
      shots: shots.length,
    };
  });
}

/**
 * Counts each outcome of a circuit's shots
 *
 * @param shots - each shot's bits as hex, e.g. "0x3"
 * @param numClbits - the circuit's classical bits, to which each outcome is padded
 * @returns the outcomes seen, as bitstrings with bit 0 rightmost, in order
 */
export function countOutcomes(
  shots: string[],
  numClbits: number,
): OutcomeCount[] {
  const counts = new Map<string, number>();
  for (const shot of shots) {
    const outcome = BigInt(shot).toString(2).padStart(numClbits, "0");
    counts.set(outcome, (counts.get(outcome) ?? 0) + 1);
  }
  return [...counts.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([outcome, count]) => ({ outcome, count }));
}
