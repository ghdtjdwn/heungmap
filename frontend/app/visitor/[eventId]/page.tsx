import { VisitorEventDetail } from "@/components/visitor-event-detail";

export default async function VisitorEventPage({ params }: { params: Promise<{ eventId: string }> }) {
  const { eventId } = await params;
  return <VisitorEventDetail eventId={eventId} />;
}
