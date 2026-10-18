/**
 * StepRail — the four steps of the project, always visible (moved out of pages/InteriorProject.jsx for the
 * Pathon v3 workspace frame, so the panel contents that render inside the project page do not import the
 * page back).
 */
import React from 'react';
import { useTranslation } from 'react-i18next';
import LearningJournal from '@/components/project/LearningJournal';

// ── Step bar ──────────────────────────────────────────────────────────────────
//
// „Rimo kelionė" (2026-09-04): ONE path, FOUR steps, always visible —
// Brėžinys → Patikra → Sąmata → Siųsti. Not tabs: a tab set says "these are
// four unrelated places"; a numbered step row says "this is the order, and you
// are here". Every step is clickable (nobody is ever trapped), the current one
// is the loud one, and each step's own exit is ONE big button at the bottom.
//
// The Brėžinys step is ALWAYS present. Hiding it when a project has no PDF was
// a dead end: the "prisegti brėžinį" affordance lives INSIDE that step, so a
// project that lost its drawing could never get one back.

export const STEPS = ['brezinys', 'patikra', 'samata', 'siusti'];

// Pathon v3 frame (A5, audit B11): ONE cue per step — its number and its name; no icon beside them and no
// coloured disc. The step he is on is in ink with a 2 px underline; the others are quieter, done ones a
// little less quiet than the ones ahead.
export function StepBar({ step, setStep, hasPdf, projectId = null }) {
  const { t } = useTranslation();
  const currentIdx = STEPS.indexOf(step);
  return (
    <nav
      aria-label={t('project.steps.navLabel')}
      className="flex items-center border-b border-border overflow-x-auto bg-card"
      style={{ paddingLeft: 12, paddingRight: 12, gap: 2 }}
    >
      {STEPS.map((id, i) => {
        const isActive = step === id;
        const isDone = i < currentIdx;
        return (
          <React.Fragment key={id}>
            {i > 0 && (
              <span aria-hidden className="text-muted-foreground/50 shrink-0" style={{ fontSize: 16 }}>›</span>
            )}
            <button
              onClick={() => setStep(id)}
              title={id === 'brezinys' && !hasPdf
                ? t('project.steps.brezinysAttachTitle')
                : t(`project.steps.titles.${id}`)}
              aria-current={isActive ? 'step' : undefined}
              data-testid={`step-${id}`}
              /* 44 px tall, 16 px label — the whole product is aimed at 35–60
                 year old eyes and hands (design §5). */
              className={`flex items-center shrink-0 whitespace-nowrap border-b-2 -mb-px transition-colors ${
                isActive
                  ? 'border-foreground text-foreground font-semibold'
                  : isDone
                    ? 'border-transparent text-foreground/75 hover:text-foreground'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
              style={{ minHeight: 44, padding: '0 14px', gap: 8, fontSize: 16 }}
            >
              <span aria-hidden className="tabular">{i + 1}</span>
              {t(`project.steps.${id}`)}
            </button>
          </React.Fragment>
        );
      })}
      {/* „Įsiminta: N" — the learning journal, on every step (togal-v2 W11) */}
      {projectId && <LearningJournal projectId={projectId} />}
    </nav>
  );
}
