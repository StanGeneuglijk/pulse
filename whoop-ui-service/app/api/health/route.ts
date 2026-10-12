import { NextResponse } from "next/server";
import { checkInsightHealth } from "@/lib/insightClient";
import { checkNutritionHealth } from "@/lib/nutritionClient";
import { checkWhoopHealth } from "@/lib/whoopClient";

export async function GET() {
  const [whoop, insight, nutrition] = await Promise.all([
    checkWhoopHealth(),
    checkInsightHealth(),
    checkNutritionHealth(),
  ]);
  return NextResponse.json({ whoop, insight, nutrition });
}
