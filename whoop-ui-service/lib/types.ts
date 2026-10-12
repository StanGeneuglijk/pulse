// Wire shapes of the three backends' camelCase JSON responses.
// Timestamps are naive UTC ISO strings — parse them with `parseUtc` (lib/format.ts).

interface WhoopRecordBase {
  id: string;
  whoopRecordId: string;
  score: number | null;
  recordedAt: string;
  scoreState: string | null;
}

export interface RecoveryRecord extends WhoopRecordBase {
  sleepId: string | null;
  userCalibrating: boolean | null;
  restingHeartRate: number | null;
  hrvRmssdMilli: number | null;
  spo2Percentage: number | null;
  skinTempCelsius: number | null;
}

export interface SleepRecord extends WhoopRecordBase {
  cycleId: string | null;
  start: string | null;
  end: string | null;
  nap: boolean | null;
  inBedMilli: number | null;
  awakeMilli: number | null;
  lightSleepMilli: number | null;
  slowWaveSleepMilli: number | null;
  remSleepMilli: number | null;
  sleepCycleCount: number | null;
  disturbanceCount: number | null;
  sleepNeededMilli: number | null;
  respiratoryRate: number | null;
  sleepConsistencyPercentage: number | null;
  sleepEfficiencyPercentage: number | null;
}

export interface WorkoutRecord extends WhoopRecordBase {
  start: string | null;
  end: string | null;
  sportName: string | null;
  averageHeartRate: number | null;
  maxHeartRate: number | null;
  kilojoule: number | null;
  percentRecorded: number | null;
  distanceMeter: number | null;
  altitudeGainMeter: number | null;
  zoneDurationsMilli: (number | null)[] | null;
}

export interface CycleRecord extends WhoopRecordBase {
  start: string | null;
  end: string | null;
  kilojoule: number | null;
  averageHeartRate: number | null;
  maxHeartRate: number | null;
}

export interface Profile {
  firstName: string | null;
  lastName: string | null;
  heightMeter: number | null;
  weightKilogram: number | null;
  maxHeartRate: number | null;
}

export interface SyncTriggerResponse {
  queued: boolean;
}

export interface SyncLogEntry {
  status: string;
  triggerSource: string;
  recoveriesSynced: number;
  sleepSynced: number;
  workoutsSynced: number;
  cyclesSynced: number;
  durationMs: number;
  errorMessage: string | null;
  createdAt: string;
}

export interface AuthExchangeResponse {
  connected: boolean;
  userId: string;
  readToken: string | null;
}

// whoop-insight-service
export type InsightPeriod = "daily" | "weekly" | "monthly";

export interface InsightRecord {
  id: string;
  userId: string;
  periodType: InsightPeriod;
  periodStart: string;
  periodEnd: string;
  promptVersion: string;
  modelName: string;
  content: string;
  createdAt: string;
}

export interface InsightUsage {
  totalGenerated: number;
  generatedByPeriod: Record<string, number>;
  activityCount: number;
  spendUsd: number;
  lastGeneratedAt: string | null;
}

// whoop-nutrition-service
export interface MealItem {
  name: string;
  quantity: string;
  calories: number;
  proteinG: number;
  carbsG: number;
  fatG: number;
}

export interface MealProposal {
  description: string;
  loggedAt: string;
  items: MealItem[];
  totalCalories: number;
  totalProteinG: number;
  totalCarbsG: number;
  totalFatG: number;
  fiberG: number | null;
  sugarG: number | null;
  sodiumMg: number | null;
}

export interface ChatResponse {
  conversationId: string;
  reply: string | null;
  pendingMeal: MealProposal | null;
  transcript?: string | null;
}

export interface NutritionLogRecord {
  id: string;
  userId: string;
  conversationId: string | null;
  description: string;
  loggedAt: string;
  calories: number;
  proteinG: number;
  carbsG: number;
  fatG: number;
  fiberG: number | null;
  sugarG: number | null;
  sodiumMg: number | null;
  modelName: string;
  createdAt: string;
}

export type GoalType = "weight_loss" | "maintenance" | "weight_gain" | "muscle_gain";

export interface NutritionGoal {
  id: string;
  goalType: GoalType;
  targetCalories: number | null;
  targetProteinG: number | null;
  targetCarbsG: number | null;
  targetFatG: number | null;
  notes: string | null;
  isActive: boolean;
  createdAt: string;
}

export interface SetGoalBody {
  goalType: GoalType;
  targetCalories: number | null;
  targetProteinG: number | null;
  targetCarbsG: number | null;
  targetFatG: number | null;
  notes: string | null;
}
