/** A pulse line inside a gradient tile. */
export function Logomark({ size = 36 }: { size?: number }) {
  return (
    <div
      className="flex items-center justify-center rounded-xl bg-brand-gradient p-[1.5px]"
      style={{ width: size, height: size }}
    >
      <div className="flex h-full w-full items-center justify-center rounded-[10px] bg-base">
        <svg viewBox="0 0 24 24" fill="none" style={{ width: size * 0.6, height: size * 0.6 }}>
          <defs>
            <linearGradient id="pulse-mark" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#22E57A" />
              <stop offset="100%" stopColor="#FF6B3D" />
            </linearGradient>
          </defs>
          <path
            d="M2 12h4l2.5-6 4 12 3-9 2 3H22"
            stroke="url(#pulse-mark)"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
    </div>
  );
}
