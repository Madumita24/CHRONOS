import { AnalysisPage } from "@/components/phase6/analysis-page";

export default async function CertifiedAnalysisPage({ params }: { params: Promise<{ analysisId: string }> }) {
  const { analysisId } = await params;
  return <AnalysisPage analysisId={analysisId} />;
}
