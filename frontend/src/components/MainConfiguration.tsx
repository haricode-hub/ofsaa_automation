'use client'

import { useEffect, useMemo, useState } from 'react'

export interface MainConfigData {
  host: string
  username: string
  password: string
  fic_home: string
  java_home: string
  java_bin: string
  oracle_sid: string
}

interface MainConfigurationProps {
  enabled: boolean
  data: MainConfigData
  errors: Record<string, string>
  onChange: (data: MainConfigData) => void
}

export function MainConfiguration({ enabled, data, errors, onChange }: MainConfigurationProps) {
  const handleInputChange = (field: keyof MainConfigData) => (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    onChange({ ...data, [field]: e.target.value })
  }

  if (!enabled) {
    return null
  }

  return (
    <section className="rounded-xl border border-border bg-bg-secondary/40 p-4 lg:p-5 space-y-4">
      <details className="group">
        <summary className="list-none cursor-pointer select-none flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-bold text-text-primary uppercase tracking-wider">
              Main Configuration
            </div>
            <div className="text-xs text-text-muted mt-1">
              Host access and profile defaults.
            </div>
          </div>
          <div className="text-xs font-mono text-text-muted group-open:hidden">OPEN</div>
          <div className="text-xs font-mono text-text-muted hidden group-open:block">CLOSE</div>
        </summary>

        <div className="mt-5 space-y-4">
          <div className="space-y-2">
            <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
              Target Host
            </label>
            <input
              type="text"
              value={data.host}
              onChange={handleInputChange('host')}
              placeholder="192.168.1.100"
              className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              required
            />
            {errors.host && <p className="text-xs text-error">{errors.host}</p>}
          </div>

          <div className="space-y-2">
            <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
              SSH Username
            </label>
            <input
              type="text"
              value={data.username}
              onChange={handleInputChange('username')}
              placeholder="oracle"
              className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              required
            />
            {errors.username && <p className="text-xs text-error">{errors.username}</p>}
          </div>

          <div className="space-y-2">
            <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
              SSH Password
            </label>
            <input
              type="password"
              value={data.password}
              onChange={handleInputChange('password')}
              placeholder="********"
              className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              required
            />
            {errors.password && <p className="text-xs text-error">{errors.password}</p>}
          </div>

          <div className="border-t border-border pt-6 space-y-4">
            <div className="text-sm font-bold text-text-primary uppercase tracking-wider mb-1">
              Profile Configuration
            </div>

            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                FIC_HOME Path
              </label>
              <input
                type="text"
                value={data.fic_home}
                onChange={handleInputChange('fic_home')}
                placeholder="/u01/OFSAA/FICHOME"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
                required
              />
              {errors.fic_home && <p className="text-xs text-error">{errors.fic_home}</p>}
            </div>

            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                JAVA_HOME (Optional - Auto-detected if empty)
              </label>
              <input
                type="text"
                value={data.java_home}
                onChange={handleInputChange('java_home')}
                placeholder="/usr/lib/jvm/java-11-openjdk"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
              {errors.java_home && <p className="text-xs text-error">{errors.java_home}</p>}
            </div>

            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                JAVA_BIN Path (Optional)
              </label>
              <input
                type="text"
                value={data.java_bin}
                onChange={handleInputChange('java_bin')}
                placeholder="/usr/bin/java"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
              {errors.java_bin && <p className="text-xs text-error">{errors.java_bin}</p>}
            </div>

            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                Oracle SID
              </label>
              <input
                type="text"
                value={data.oracle_sid}
                onChange={handleInputChange('oracle_sid')}
                placeholder="ORCL"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
                required
              />
              {errors.oracle_sid && <p className="text-xs text-error">{errors.oracle_sid}</p>}
            </div>
          </div>
        </div>
      </details>
    </section>
  )
}
