import { VisitorEventDetail } from "@/components/visitor-event-detail";
import "./visitor-detail.css";

export default async function VisitorEventPage({ params }: { params: Promise<{ eventId: string }> }) {
  const { eventId } = await params;
  return <VisitorEventDetail eventId={eventId} />;
}
