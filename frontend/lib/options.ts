export const PLANNER_TYPES = [
  ["local_government", "지자체"], ["public_agency", "공공기관"], ["company", "기업"],
  ["event_agency", "행사 대행사"], ["performance_agency", "공연기획사"],
  ["venue_operator", "장소 운영자"], ["club_or_group", "동아리·단체"],
  ["independent_planner", "독립 기획자"], ["artist", "가수·아티스트"], ["other", "기타"],
] as const;

export const PLANNING_STAGES = [
  ["idea", "아이디어"], ["research", "사전 조사"], ["budget_application", "예산 신청"],
  ["venue_search", "장소 탐색"], ["booking", "섭외"], ["marketing_preparation", "홍보 준비"],
  ["ticket_sales", "예매 중"], ["final_preparation", "최종 준비"],
] as const;

export const EVENT_TYPES = [
  ["festival", "축제"], ["local_event", "지역 행사"], ["concert", "콘서트"],
  ["club_performance", "클럽 공연"], ["exhibition", "전시"], ["conference", "컨퍼런스"],
  ["experience", "체험"], ["market", "플리마켓"], ["other", "기타"],
] as const;

export const PURPOSES = [
  ["profit", "수익"], ["regional_revitalization", "지역 활성화"], ["tourism", "관광 유입"],
  ["brand", "브랜드 홍보"], ["fandom", "팬 확대"], ["community", "커뮤니티"],
  ["culture", "문화 향유"], ["education", "교육"], ["social_contribution", "사회공헌"], ["other", "기타"],
] as const;

export const AUDIENCES = [
  ["child", "어린이"], ["teen", "청소년"], ["young_adult", "청년"],
  ["middle_aged", "중장년"], ["senior", "고령자"], ["family", "가족"],
  ["local_resident", "지역 주민"], ["domestic_tourist", "국내 관광객"],
  ["foreign_tourist", "외국인 관광객"], ["fandom", "기존 팬"], ["other", "기타"],
] as const;

export const REGIONS = [
  ["1", "서울"], ["2", "인천"], ["3", "대전"], ["4", "대구"], ["5", "광주"],
  ["6", "부산"], ["7", "울산"], ["8", "세종"], ["31", "경기"], ["32", "강원"],
  ["33", "충북"], ["34", "충남"], ["35", "경북"], ["36", "경남"], ["37", "전북"],
  ["38", "전남"], ["39", "제주"],
] as const;

export const MARKETING_CHANNELS = ["인스타그램", "유튜브", "틱톡", "블로그", "지역 커뮤니티", "보도자료", "옥외 홍보"];

const ENVIRONMENTS = [["indoor", "실내"], ["outdoor", "실외"], ["mixed", "실내·실외 혼합"], ["undecided", "미정"]] as const;
const ALL_OPTIONS = [...PLANNER_TYPES, ...PLANNING_STAGES, ...EVENT_TYPES, ...PURPOSES, ...AUDIENCES, ...ENVIRONMENTS] as readonly (readonly [string, string])[];

export function optionLabel(value: string | undefined): string {
  if (!value) return "미정";
  return ALL_OPTIONS.find(([key]) => key === value)?.[1] ?? value;
}

export function audienceLabel(value: string): string {
  return AUDIENCES.find(([key]) => key === value)?.[1] ?? value;
}

export function seatingLabel(value: string): string {
  return ({ seated: "좌석", standing: "스탠딩", mixed: "좌석·스탠딩 혼합", unknown: "미정" } as Record<string, string>)[value] ?? value;
}

export function regionFromCode(code: string): { area_code: string; display_name: string } | undefined {
  const region = REGIONS.find(([value]) => value === code);
  return region ? { area_code: region[0], display_name: region[1] } : undefined;
}
