// Original inline SVG icons. Decorative by default (aria-hidden); label the
// surrounding control instead.

interface IconProps {
  className?: string;
}

export function FlameIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path
        fill="currentColor"
        d="M12.6 2.2c.4 3-1.1 4.6-2.5 6.1C8.6 9.9 7 11.6 7 14.4A5 5 0 0 0 12 19.5a5 5 0 0 0 5-5.1c0-1.8-.7-3.2-1.6-4.3-.2 1.3-.9 2.3-2 2.8.5-2.9-.2-6.4-.8-10.7Z"
      />
      <path
        fill="#FFE08A"
        d="M12 13c.9 1 1.6 2 1.6 3.1A1.7 1.7 0 0 1 12 17.8a1.7 1.7 0 0 1-1.6-1.7c0-1.1.7-2.1 1.6-3.1Z"
      />
    </svg>
  );
}

export function HeartIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path
        fill="currentColor"
        d="M12 20.6s-7.8-4.6-9.2-9.4C1.9 8 3.8 4.6 7.3 4.6c2 0 3.5 1.1 4.7 2.7 1.2-1.6 2.7-2.7 4.7-2.7 3.5 0 5.4 3.4 4.5 6.6-1.4 4.8-9.2 9.4-9.2 9.4Z"
      />
      <ellipse cx="7.6" cy="8.6" rx="1.6" ry="1.1" fill="#fff" opacity=".55" transform="rotate(-30 7.6 8.6)" />
    </svg>
  );
}

export function GemIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path fill="currentColor" d="M6.5 3.5h11L22 9l-10 11.5L2 9l4.5-5.5Z" />
      <path fill="#fff" opacity=".4" d="M6.5 3.5 9 9H2l4.5-5.5Zm5.5 0L9 9h6l-3-5.5Z" />
    </svg>
  );
}

export function HomeIcon({ className = "h-7 w-7" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path
        fill="currentColor"
        d="M11.3 3.3a1 1 0 0 1 1.4 0l8 7.4c.6.6.2 1.7-.7 1.7H19v7a1.6 1.6 0 0 1-1.6 1.6H15v-5.2a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1V21H6.6A1.6 1.6 0 0 1 5 19.4v-7H4c-.9 0-1.3-1.1-.7-1.7l8-7.4Z"
      />
    </svg>
  );
}

export function TrophyIcon({ className = "h-7 w-7" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path
        fill="currentColor"
        d="M7 3h10v2h3a1 1 0 0 1 1 1v1.5A4.5 4.5 0 0 1 16.8 12 5 5 0 0 1 13 15v2.5h3a1 1 0 0 1 1 1V21H7v-2.5a1 1 0 0 1 1-1h3V15a5 5 0 0 1-3.8-3A4.5 4.5 0 0 1 3 7.5V6a1 1 0 0 1 1-1h3V3Zm10 4v3.2A2.5 2.5 0 0 0 19 7.5V7h-2ZM5 7v.5a2.5 2.5 0 0 0 2 2.7V7H5Z"
      />
    </svg>
  );
}

export function UserIcon({ className = "h-7 w-7" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <circle cx="12" cy="8" r="4.2" fill="currentColor" />
      <path fill="currentColor" d="M3.8 20.2c.8-4.1 4.2-6.4 8.2-6.4s7.4 2.3 8.2 6.4a1 1 0 0 1-1 1.2H4.8a1 1 0 0 1-1-1.2Z" />
    </svg>
  );
}

export function SettingsIcon({ className = "h-7 w-7" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path
        fill="currentColor"
        fillRule="evenodd"
        d="M10.3 2.5h3.4l.5 2.5 1.6.9 2.4-.9 1.7 2.9-1.9 1.7v1.8l1.9 1.7-1.7 2.9-2.4-.9-1.6.9-.5 2.5h-3.4l-.5-2.5-1.6-.9-2.4.9L4.1 17l1.9-1.7v-1.8L4.1 11.8 5.8 8.9l2.4.9 1.6-.9.5-2.5ZM12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Z"
      />
    </svg>
  );
}

export function LockIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path fill="currentColor" d="M7 10V7.5a5 5 0 0 1 10 0V10h.5A1.5 1.5 0 0 1 19 11.5v8a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 5 19.5v-8A1.5 1.5 0 0 1 6.5 10H7Zm2.5 0h5V7.5a2.5 2.5 0 0 0-5 0V10Z" />
    </svg>
  );
}

export function CheckIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" d="m5 12.5 4.5 4.5L19 7.5" />
    </svg>
  );
}

export function CloseIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" d="M6 6l12 12M18 6 6 18" />
    </svg>
  );
}

export function StarIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path fill="currentColor" d="m12 2.8 2.8 5.8 6.3.9-4.6 4.4 1.1 6.3L12 17.2l-5.6 3 1.1-6.3-4.6-4.4 6.3-.9L12 2.8Z" />
    </svg>
  );
}

export function BoltIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path fill="currentColor" d="M13.5 2 4.8 13.2c-.4.5 0 1.3.7 1.3H11l-1 7.5 8.7-11.2c.4-.5 0-1.3-.7-1.3H12.5l1-7.5Z" />
    </svg>
  );
}

export function TargetIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="2.5" />
      <circle cx="12" cy="12" r="5" fill="none" stroke="currentColor" strokeWidth="2.5" />
      <circle cx="12" cy="12" r="1.8" fill="currentColor" />
    </svg>
  );
}
