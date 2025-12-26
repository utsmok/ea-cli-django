# Platform Improvement Plans - Master Overview

This document provides a high-level overview of 7 improvement tasks for the Easy Access Django platform, including implementation order, parallelization strategy, and current status.

## Quick Reference

| Task | Status | Complexity | Time | Dependencies | Branch |
|------|--------|-----------|------|--------------|--------|
| 1. Redis Caching | ✅ Complete | Medium | 1-2 days | None | `main` |
| 2. Model Separation | ✅ Complete | **High** | 3-4 days | None | `main` |
| 3. Settings System | ✅ Complete | **High** | 4-5 days | Task 2 helpful | `main` |
| 4. Template Partials | ✅ Complete | Low | 1 day | None | `main` |
| 5. Error Handling | ✅ Complete | Medium | 2-3 days | Task 3 (API keys) | `main` |
| 6. Table Enhancements | ✅ Complete | Med-High | 2-3 days | Tasks 2,3,4 helpful | `main` |
| 7. Styling Fixes | ✅ Complete | Low-Med | 1-2 days | None | `main` |

## Current Status Summary

### ✅ Completed (Tasks 1-7)
- **Task 1 (Redis):** Fully implemented with auto-invalidation and cache statistics.
- **Task 2 (Models):** QlikItem mirror table implemented with merge-logic processor.
- **Task 3 (Settings):** Settings app implemented with YAML import/export and admin UI.
- **Task 4 (Templates):** Template partials strategy verified and applied.
- **Task 5 (Errors):** Comprehensive error handling and retry logic for external APIs.
- **Task 6 (Table):** Detail modal, slide-out panel, and enhanced row interactions.
- **Task 7 (Styling):** UT brand colors fully implemented.

## Key Implementation Insights

### Lesson 1: Django 6.0 Template Partials
**Feature:** Django 6.0 includes built-in template partials with `{% partialdef %}` / `{% partial %}` syntax.
**Benefits:**
- Better encapsulation (only passed variables available)
- Default parameters supported
- Direct access via `template.html#partial_name` for AJAX/HTMX
- Context isolation (no pollution from parent context)
- Inline rendering support

**Implementation:**
```django
{# Define partial #}
{% partialdef status_badge status_type status_text %}
<span class="badge badge-{{ status_type }}">{{ status_text }}</span>
{% endpartialdef %}

{# Use partial #}
{% partial status_badge status_type="success" status_text="Done" %}

{# Direct rendering for HTMX #}
render(request, "components/partials.html#status_badge", context)
```

**Recommendation:** Migrate high-priority components (status_badge, workflow_tabs, editable_cell) to use partials for better HTMX integration.

### Lesson 2: Redis Caching Infrastructure
**Status:** Well-designed cache service exists with sync/async decorators.
**Missing:**
- CACHES configuration in settings.py
- Application of cache decorators to services
- Cache invalidation logic

**Next Steps:** Add django-redis package, configure CACHES, apply decorators to query_service, osiris, and canvas services.

### Lesson 3: Styling Completed Successfully
**Success:** UT brand implementation resolved all contrast issues.
**Impact:** All buttons now use proper UT colors with white text, badges use semantic UT colors.
**Result:** Solid visual foundation for remaining UI work.

## Parallelization Strategy

### Phase 1: Complete Foundation (Can Start Immediately)

**Branches:** `feature/redis-caching`, `feature/django-partials`

- **Task 1:** Redis Caching - Complete implementation (40% done)
  - Add `django-redis` package
  - Configure CACHES in settings.py
  - Apply cache decorators to services
  - Add cache invalidation

- **Task 4:** Template Partials - Native Django 6.0 feature
  - Create `components/partials.html` with `{% partialdef %}`
  - Convert high-priority components (status_badge, workflow_tabs, editable_cell)
  - Update dashboard to use `{% partial %}` syntax
  - Use direct partial rendering for HTMX (`template.html#partial_name`)

✅ These tasks can be done in parallel on different branches

### Phase 2: Data Layer (Sequential)

**Branch:** `feature/qlikitem-model`

- **Task 2:** Model Separation - QlikItem creation
  - ⚠️ **Maintenance window required**
  - Complex data migration
  - Must be completed before Task 3 for clean architecture

### Phase 3: Configuration & Reliability (Can Overlap)

**Branches:** `feature/settings-system`, `feature/error-handling`

- **Task 3:** Settings System - Models + YAML + UI + API validation
- **Task 5:** Error Handling - Retry logic, error visibility, Canvas fixes
  - Can start after Task 3's API key feature is ready
  - Integrates with settings system for API validation

### Phase 4: UI Polish (Sequential)

**Branch:** `feature/table-enhancements`

- **Task 6:** Table Enhancements - Sorting, slide-out, full-width
  - Builds on existing modal (30% done)
  - Can work independently once models are stable

## Dependency Graph

```
Task 1 (Redis) ──────────────────────────────────────┐
                                                       │
Task 2 (Models) ─────┬────────────────────────────────┤
                     │                                │
Task 3 (Settings) ◀──┘                                │
                     │                                │
Task 4 (Partials) ───┴───────────────────┬────────────┤
                                          │            │
Task 5 (Errors) ◀─────────────────────────┘            │
                                                       │
Task 6 (Table) ◀──────────────────────────────────────┘
      │
Task 7 (Styles) ───────────────────────────────────┘ ✅ DONE
```

## Individual Task Plans

Detailed plans for each task are located in `/docs/plans/`:

1. **[01-redis-caching.md](docs/plans/01-redis-caching.md)** - Cache configuration, decorators, invalidation (40% complete)
2. **[02-model-separation.md](docs/plans/02-model-separation.md)** - QlikItem model, migrations, query updates
3. **[03-settings-system.md](docs/plans/03-settings-system.md)** - Settings models, YAML, UI, API validation
4. **[04-template-partials.md](docs/plans/04-template-partials.md)** - Template strategy (revised - Django 6.0 lacks built-in partials)
5. **[05-error-handling.md](docs/plans/05-error-handling.md)** - Retry logic, error visibility, Canvas fixes
6. **[06-table-enhancements.md](docs/plans/06-table-enhancements.md)** - Sorting, filtering, slide-out panel (30% complete)
7. **[07-styling-fixes.md](docs/plans/README.md)** - Color fixes, contrast improvements ✅ **COMPLETE**

## Deployment Order

### Phase 1: Complete Foundation
**Deploy Tasks 1 & 4 together**
- Low risk, high value
- Sets up infrastructure
- Estimated: 1-2 days each

### Phase 2: Deploy Data Layer
**Deploy Task 2**
- ⚠️ **Maintenance window required**
- Database migration
- Extensive testing needed
- Estimated: 3-4 days

### Phase 3: Deploy Configuration
**Deploy Tasks 3 & 5 together**
- Settings infrastructure
- Error handling improvements
- Estimated: 4-5 days (Task 3) + 2-3 days (Task 5)

### Phase 4: Deploy UI Polish
**Deploy Task 6**
- User-facing improvements
- Lower risk
- Estimated: 2-3 days

## Testing Strategy

### Unit Tests Required
- Task 1: Cache integration tests (infrastructure exists, need usage tests)
- Task 2: Model relationships, migrations
- Task 3: Settings CRUD, YAML import/export
- Task 5: Retry logic, error categorization

### Integration Tests Required
- Task 2: Full ingest pipeline after model changes
- Task 3: Settings propagation to all components
- Task 5: Error recovery in enrichment tasks
- Task 6: Table sorting/filtering with large datasets

### Manual Testing Required
- Task 4: Component rendering with chosen approach
- Task 6: Responsive design, keyboard navigation
- All tasks: End-to-end workflow verification

## Rollback Strategy

| Task | Rollback Approach |
|------|-------------------|
| 1 | Disable caching (USE_CACHE env variable) |
| 2 | Reverse migrations (keep migration files) |
| 3 | Export DB settings to YAML before deploy |
| 4 | Git revert (no database changes) |
| 5 | Feature flag for new error behavior |
| 6 | Git revert (template/view changes) |
| 7 | ✅ Complete - no rollback needed |

## Critical Files Reference

### Settings & Config
- `src/config/settings.py` - Django settings (Tasks 1, 3) - **Needs CACHES config**
- `src/config/university.py` - University config (Task 3)

### Services (Existing - Need Integration)
- `src/apps/core/services/cache_service.py` - ✅ Cache utilities complete (Task 1)
- `src/apps/core/services/canvas.py` - Canvas API (Tasks 1, 3, 5) - **Needs caching & error handling**
- `src/apps/core/services/osiris.py` - Osiris scraping (Task 1) - **Needs caching**
- `src/apps/dashboard/services/query_service.py` - Query service (Tasks 1, 6) - **Needs caching & sorting**

### Models
- `src/apps/core/models.py` - Core models (Task 2)
- `src/apps/ingest/models.py` - Ingestion models (Task 2)
- `src/apps/enrichment/models.py` - Enrichment models (Task 5)

### Templates
- `src/templates/base.html` - Base template (Task 4)
- `src/templates/dashboard/*` - Dashboard templates (Tasks 4, 6)
- `src/templates/components/*` - Component templates (Tasks 4, 6)

### Styles (Complete ✅)
- `src/static/css/ut-brand.css` - UT brand colors (Task 7 - DONE)

## Next Steps

### Immediate Actions

1. **Finish Redis Caching (Task 1):**
   ```bash
   uv add django-redis
   # Add CACHES to settings.py
   # Apply decorators to services
   ```

2. **Implement Django 6.0 Partials (Task 4):**
   - Create `components/partials.html` with partialdefs
   - Convert: status_badge, workflow_tabs, editable_cell, filter_dropdown
   - Update templates to use `{% partial %}` syntax
   - Use `template.html#partial_name` for HTMX partial updates

3. **Schedule Maintenance Window (Task 2):**
   - Plan database migration
   - Set up staging environment
   - Prepare rollback strategy

### After Foundation

4. **Start Model Separation (Task 2)** - Requires coordination
5. **Build Settings System (Task 3)** - Enables better configuration
6. **Improve Error Handling (Task 5)** - Better reliability
7. **Complete Table Enhancements (Task 6)** - Build on existing modal

## Success Metrics

Each task plan includes specific success criteria. Overall project success metrics:

- [ ] All 7 tasks complete
- [ ] Cache hit rate > 70% for expensive queries
- [ ] Page load time < 2 seconds for filtered views
- [ ] Zero data loss from model migration
- [ ] Error recovery rate > 95% for transient failures
- [ ] User satisfaction with table interactions
- [ ] Settings system supports YAML backup/restore

---

**Generated:** 2025-12-25 (Updated after Tasks 1, 4, 7 partial implementation)
**Platform:** Easy Access Django
**Version:** 2.0.0 (Updated with implementation insights)

For detailed implementation steps, see individual task plans in `/docs/plans/`.
