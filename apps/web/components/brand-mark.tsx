import { DOCMIND_ICON_128, PRODUCT_NAME } from "@/lib/brand";

export function BrandMark({ size = 36, className = "" }: { size?: number; className?: string }) {
  return (
    <span
      role="img"
      aria-label={`${PRODUCT_NAME} logo`}
      className={`inline-block shrink-0 bg-cover bg-center bg-no-repeat ${className}`}
      style={{
        width: size,
        height: size,
        backgroundImage: `url(${DOCMIND_ICON_128})`,
      }}
    />
  );
}
