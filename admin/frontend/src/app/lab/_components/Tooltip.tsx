interface TooltipProps {
  children: React.ReactNode;
  content: string;
}

export function Tooltip({ children, content }: TooltipProps) {
  return (
    <span className="group relative inline-block">
      {children}
      <span className="invisible absolute left-1/2 z-50 mb-2 w-64 -translate-x-1/2 -translate-y-full whitespace-pre-wrap rounded-lg bg-gray-900 px-3 py-2 text-xs leading-relaxed text-white shadow-lg group-hover:visible" style={{ bottom: '100%' }}>
        {content}
        <span className="absolute left-1/2 top-full -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
      </span>
    </span>
  );
}
