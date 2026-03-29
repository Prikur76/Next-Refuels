# Промпт для согласованного UI с фронтендом Next-Refuels

Скопируйте блок ниже в чат с ИИ или передайте разработчику. При необходимости добавьте ссылку на репозиторий или вставьте актуальный `frontend/app/globals.css`.

---

## Промпт (шаблон)

**Роль и задача**  
Ты — фронтенд-разработчик. Нужно реализовать интерфейс **[описание экрана или пользовательского сценария]** так, чтобы он визуально и по UX совпадал с существующим приложением **Next-Refuels**: та же типографика, семантика цветов, отступы, радиусы, поведение кнопок и фокуса, адаптив (мобильный таббар против десктопного сайдбара).

**Стек (соблюдать)**  
- **Next.js 14** (App Router), **React 18**, **TypeScript**.  
- **Tailwind CSS v4**: в глобальных стилях `@import "tailwindcss"`; утилиты Tailwind допустимы точечно (например `text-sm`, `font-semibold`, `text-[var(--muted)]`), но **основа UI — глобальные классы и CSS-переменные**, а не полностью arbitrary-утилиты.  
- **Иконки**: `lucide-react`, в навигации ориентир **18×18 px**, **stroke-width ~2.2–2.4**.  
- **Состояние и запросы**: при необходимости **TanStack React Query** (как в проекте: `staleTime`, умеренные ретраи для queries, без ретраев для mutations).  
- **Анимация смены страниц**: **Framer Motion** — `AnimatePresence` и `motion.div` с лёгким сдвигом по оси Y и плавным появлением/исчезновением (`duration` ~0.18 s).  
- **Переходы между маршрутами**: где уместно — **View Transitions API** (`document.startViewTransition` и навигация), согласованно с `view-transition-name` на корневом контейнере приложения.

**Тема и цвета**  
- Светлая и тёмная тема через **`html[data-theme="light"|"dark"]`**, синхронизация с `prefers-color-scheme` и `localStorage` (в проекте ключ `next_refuels:theme`).  
- Использовать **CSS custom properties**: `--bg`, `--text`, `--muted`, `--border`, `--surface-0`, `--surface-1`, `--surface-2`, `--primary`, `--primary-contrast`, `--danger`, `--success`, `--focus`, `--shadow-soft`.  
- Допустимы **`light-dark()`** и **`color-mix(in srgb, …)`** как в эталонных стилях.  
- Сохранить **сине-нейтральную палитру**: в светлой теме primary ~`#2563eb`, в тёмной ~`#60a5fa`.

**Типографика**  
- Основной шрифт: **system UI** — `ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`.  
- **Body: 15 px**, **line-height: 1.45**.  
- Заголовки секций: **~18 px, font-weight 700, letter-spacing ~-0.01 em** (аналог `.section-title`).  
- Подписи к полям: **~13 px, цвет `var(--muted)`, letter-spacing ~0.01 em** (аналог `.label-app`).  
- Моноширинный текст: **ui-monospace stack, ~12 px** (аналог `.mono`).  
- Язык интерфейса по умолчанию: **русский** (`lang="ru"` на `<html>`).

**Компоненты и классы (семантика проекта)**  
Опираться на те же идеи и имена классов, что в `frontend/app/globals.css`:  
- Карточки: `.card` (фон поверхности, бордер, **border-radius 14 px**, мягкая тень).  
- Кнопки: `.btn-app`, основная — `.btn-primary`; **border-radius 12 px**, `:active` с лёгким `scale`, `:focus-visible` с outline через `--focus`.  
- Поля: `.input-app`, подписи `.label-app`.  
- Скелетоны: `.skeleton` и анимация `shimmer`.  
- Контент: `.page-wrap` (**max-width ~1060 px**, по центру).  
- Вертикальные группы: `.stack` (gap **10 px**), панели действий `.toolbar`.  
- Таблицы: `.table-app` (шапка **12 px** приглушённым цветом, ячейки **13 px**).  
- При плиточной главной: `.home-grid`, `.home-tile` и варианты с градиентами (brand / violet / teal), если задача это предполагает.

**Адаптив и вёрстка**  
- Корень приложения с **container queries**: класс в духе `.app-cq-root` с `container-type: inline-size` и именем контейнера `app`.  
- **Брейкпоинт десктопной навигации ~920 px** (`@container app (min-width: 920px)`): узкий экран — нижний `.tabbar`, широкий — `.sidebar` (**272 px**, свёрнутый **74 px**).  
- Переключение блоков `.cq-mobile` / `.cq-desktop` по тому же контейнеру.  
- Для тач-интерфейса: **`touch-action: manipulation`**, отключение подсветки тапа, **`user-select: none`** там, где принято в эталонном UI.

**Доступность**  
- Фокус: **`focus-visible`** и контрастный outline.  
- Скрытый текст для скринридеров: `.visually-hidden`.  
- **`aria-label`**, **`aria-current="page"`** для активного пункта навигации, **`aria-disabled`** для отключённых кнопок.

**Чего не делать**  
- Не подменять дизайн сторонним UI-kit (MUI, Chakra и т.п.) как основу без явного требования.  
- Не заменять палитру «голым» Tailwind default вместо переменных проекта.  
- Не расходиться по радиусам: **12 px** для основных контролов, **14 px** для карточек и части селектов.

**Эталонные файлы в репозитории**  
- `frontend/app/globals.css` — канон цветов, компонентных классов и контейнерных запросов.  
- `frontend/app/layout.tsx` — тема, оболочка, `ThemeInitScript`.  
- `frontend/src/components/AppShell.tsx` — навигация, сайдбар, таббар.  
- `frontend/src/components/routing/PageTransition.tsx`, `ViewTransitionLink.tsx` — анимации и переходы.  
- `frontend/src/components/theme/ThemeToggle.tsx` — переключение темы.  
- `frontend/package.json` — версии Next, React, Tailwind, Framer Motion, React Query, Lucide, Recharts.

**Результат**  
Выдать код (страницы, компоненты, при необходимости фрагменты CSS) в описанном стиле и кратко перечислить использованные классы дизайн-системы.

---

## Как использовать

1. Замените **[описание экрана или пользовательского сценария]** на конкретную задачу.  
2. При работе вне репозитория приложите **`globals.css`** или ссылку на проект, чтобы палитра и классы не «уплыли».  
3. Документ можно обновлять при изменении дизайн-токенов в `globals.css`.
