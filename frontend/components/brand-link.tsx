import Image from "next/image";
import Link from "next/link";

export function BrandLink() {
  return <Link href="/" className="brand brand-link" aria-label="흥할지도 홈">
    <Image className="brand-logo-image" src="/assets/heungmap-logo.png" alt="흥할지도" width={900} height={269} priority />
  </Link>;
}
