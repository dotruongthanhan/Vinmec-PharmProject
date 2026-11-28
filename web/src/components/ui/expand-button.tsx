import { Maximize2 } from 'lucide-react'
import type { ComponentPropsWithRef } from 'react'
import { IconButton } from './icon-button'

export function ExpandButton({ label, ...props }: { label: string } & Omit<ComponentPropsWithRef<'button'>, 'aria-label'>) {
  return (
    <IconButton
      {...props}
      aria-label={label}
      data-expand-button=""
      size="sm"
      className="size-7 min-h-8 min-w-8"
      icon={<Maximize2 className="size-4" />}
    />
  )
}
