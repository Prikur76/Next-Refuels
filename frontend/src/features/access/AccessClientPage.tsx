"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, ChevronRight, Pencil, UserPlus, X } from "lucide-react";

import { useMeQuery } from "@/components/auth/useMe";
import { SkeletonLine } from "@/components/skeleton/Skeleton";
import { ResponsiveSelect } from "@/components/select/ResponsiveSelect";
import { useMediaQueryMinWidth } from "@/hooks/useMediaQueryMinWidth";
import {
  createAccessUser,
  getAccessRegions,
  getAccessEvents,
  getAccessUsers,
  setAccessUserRole,
  setAccessUserStatus,
  updateAccessUserPassword,
  updateAccessUserProfile,
} from "@/lib/api/endpoints";
import type {
  AccessLogOut,
  AccessRole,
  AccessUserCreateIn,
  AccessUserOut,
  RegionOut,
} from "@/lib/api/types";

type AccessFormState = {
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  role: AccessRole;
  region_id: string;
};

type EditFormState = {
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  region_id: string;
  role: AccessRole;
  is_active: boolean;
};

type EditFormErrors = {
  email?: string;
  first_name?: string;
  last_name?: string;
  phone?: string;
};

type UserSortKey = "username" | "region" | "group" | "status";
type SortDirection = "asc" | "desc";

function roleLabel(role: AccessRole): string {
  return role;
}

export function AccessClientPage() {
  const meQuery = useMeQuery();

  const isDesktop = useMediaQueryMinWidth(920);

  const access = useMemo(() => {
    const groups = meQuery.data?.groups ?? [];
    const isAdmin = groups.includes("Администратор");
    const isManager = groups.includes("Менеджер");
    const isFueler = groups.includes("Заправщик");
    const canManageAccess = isAdmin || isManager;
    return { isAdmin, isManager, isFueler, canManageAccess };
  }, [meQuery.data?.groups]);

  const [showAllUsers, setShowAllUsers] = useState(false);
  const [usersRegionFilter, setUsersRegionFilter] = useState<string>("");
  const [sortKey, setSortKey] = useState<UserSortKey>("username");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  const regionsQuery = useQuery<RegionOut[], Error>({
    queryKey: ["access", "regions"],
    queryFn: getAccessRegions,
    enabled: access.canManageAccess,
  });

  const usersQuery = useQuery<AccessUserOut[], Error>({
    queryKey: ["access", "users", showAllUsers],
    queryFn: () => getAccessUsers(showAllUsers),
    enabled: access.canManageAccess,
  });

  const eventsQuery = useQuery<AccessLogOut[], Error>({
    queryKey: ["access", "events"],
    queryFn: () => getAccessEvents(30),
    staleTime: 60_000,
    enabled: access.canManageAccess,
  });

  const [form, setForm] = useState<AccessFormState>({
    email: "",
    first_name: "",
    last_name: "",
    phone: "",
    role: "Заправщик",
    region_id: "",
  });
  const [editingUser, setEditingUser] = useState<AccessUserOut | null>(null);
  const [editForm, setEditForm] = useState<EditFormState>({
    email: "",
    first_name: "",
    last_name: "",
    phone: "",
    region_id: "",
    role: "Заправщик",
    is_active: true,
  });
  const [editErrors, setEditErrors] = useState<EditFormErrors>({});
  const [msg, setMsg] = useState<string>("");
  const [createUserFeedback, setCreateUserFeedback] = useState<string>("");
  const [editUserFeedback, setEditUserFeedback] = useState<string>("");
  const [createCredentialsText, setCreateCredentialsText] = useState<string>("");
  const [createCredentialsCopyStatus, setCreateCredentialsCopyStatus] =
    useState<string>("");
  const [editCredentialsText, setEditCredentialsText] = useState<string>("");
  const [editCredentialsCopyStatus, setEditCredentialsCopyStatus] =
    useState<string>("");
  const [isCreateUserModalOpen, setIsCreateUserModalOpen] = useState(false);
  const [isAccessEventsExpanded, setIsAccessEventsExpanded] = useState(false);

  function validateEditForm(payload: EditFormState): EditFormErrors {
    const errors: EditFormErrors = {};
    if (!payload.email.trim()) {
      errors.email = "Укажите email.";
    }
    if (!payload.first_name.trim()) {
      errors.first_name = "Укажите имя.";
    }
    if (!payload.last_name.trim()) {
      errors.last_name = "Укажите фамилию.";
    }
    if (!payload.phone.trim()) {
      errors.phone = "Укажите телефон.";
    }
    return errors;
  }

  function setCreateCredentialsCopyStatusWithAutoClear(message: string): void {
    setCreateCredentialsCopyStatus(message);
    window.setTimeout(() => {
      setCreateCredentialsCopyStatus("");
    }, 4000);
  }

  function setEditCredentialsCopyStatusWithAutoClear(message: string): void {
    setEditCredentialsCopyStatus(message);
    window.setTimeout(() => {
      setEditCredentialsCopyStatus("");
    }, 4000);
  }

  const currentUserId = meQuery.data?.id;

  function isAdminUser(user: AccessUserOut): boolean {
    return user.groups.includes("Администратор");
  }

  const otherActiveAdminsCount = (() => {
    if (!usersQuery.data || currentUserId === undefined) return 0;
    return usersQuery.data.filter(
      (u) => u.id !== currentUserId && u.is_active && isAdminUser(u)
    ).length;
  })();

  const createUserMutation = useMutation({
    mutationFn: async (args: {
      payload: AccessUserCreateIn;
      role: AccessRole;
    }) => {
      const created = await createAccessUser(args.payload);
      if (args.role !== "Заправщик") {
        await setAccessUserRole(created.id, args.role);
      }
      return created;
    },
    onSuccess: async (created) => {
      const passwordValue = created.temporary_password || "";
      if (passwordValue) {
        setCreateCredentialsText(
          `Логин: ${created.username}\nПароль: ${passwordValue}`
        );
        setCreateCredentialsCopyStatus("");
        setCreateUserFeedback(
          `Пароль пользователя ${created.username} обновлен.\nЛогин: ${created.username}\nПароль: ${passwordValue}`
        );
      } else {
        setCreateCredentialsText("");
        setCreateCredentialsCopyStatus("");
        setCreateUserFeedback(`Пользователь создан (${created.username}).`);
      }
      setForm({
        email: "",
        first_name: "",
        last_name: "",
        phone: "",
        role: "Заправщик",
        region_id: "",
      });
      await usersQuery.refetch();
    },
    onError: (err) => {
      setCreateUserFeedback((err as Error).message || "Ошибка создания пользователя.");
    },
  });

  const updateProfileMutation = useMutation({
    mutationFn: async (args: {
      userId: number;
      payload: EditFormState;
      currentUser: AccessUserOut;
    }) => {
      const regionValue = args.payload.region_id.trim();
      const regionId = regionValue ? Number(regionValue) : undefined;
      const emailValue = args.payload.email.trim();
      const profilePayload: {
        email?: string;
        first_name?: string;
        last_name?: string;
        phone?: string;
        region_id?: number;
      } = {
        first_name: args.payload.first_name.trim(),
        last_name: args.payload.last_name.trim(),
        phone: args.payload.phone.trim(),
      };

      if (emailValue) {
        profilePayload.email = emailValue;
      }

      if (access.isAdmin && regionId) {
        profilePayload.region_id = regionId;
      }

      const updatedUser = await updateAccessUserProfile(args.userId, {
        ...profilePayload,
      });
      if (updatedUser.is_active !== args.payload.is_active) {
        await setAccessUserStatus(args.userId, args.payload.is_active);
      }
      if (userRole(updatedUser) !== args.payload.role) {
        await setAccessUserRole(args.userId, args.payload.role);
      }
      return updatedUser;
    },
    onSuccess: async () => {
      setEditingUser(null);
      await usersQuery.refetch();
    },
    onError: (err) => {
      setMsg((err as Error).message || "Не удалось сохранить изменения.");
    },
  });

  const updatePasswordMutation = useMutation({
    mutationFn: async (args: { userId: number; generateTemporary: boolean }) =>
      updateAccessUserPassword(args.userId, {
        generate_temporary: args.generateTemporary,
      }),
    onSuccess: (payload) => {
      const passwordValue = payload.temporary_password || "";
      if (passwordValue) {
        setEditCredentialsText(
          `Логин: ${payload.username}\nПароль: ${passwordValue}`
        );
        setEditCredentialsCopyStatus("");
        setEditUserFeedback(
          `Пароль пользователя ${payload.username} обновлен.\nЛогин: ${payload.username}\nПароль: ${passwordValue}`
        );
      } else {
        setEditCredentialsText("");
        setEditCredentialsCopyStatus("");
        setEditUserFeedback(
          "Пароль обновлен. При следующем входе пользователь должен сменить пароль."
        );
      }
    },
    onError: (err) => {
      setEditUserFeedback((err as Error).message || "Не удалось обновить пароль.");
    },
  });

  function userRole(user: AccessUserOut): AccessRole {
    if (user.groups.includes("Администратор")) {
      return "Администратор";
    }
    if (user.groups.includes("Менеджер")) {
      return "Менеджер";
    }
    return "Заправщик";
  }

  function roleTextColor(role: AccessRole): string {
    if (role === "Администратор") return "#7c3aed";
    if (role === "Менеджер") return "#0f766e";
    return "#1d4ed8";
  }

  function handleSortClick(nextKey: UserSortKey): void {
    if (sortKey === nextKey) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(nextKey);
    setSortDirection("asc");
  }

  function sortMark(key: UserSortKey): string {
    if (sortKey !== key) return "";
    return sortDirection === "asc" ? " ↑" : " ↓";
  }

  const filteredUsers = useMemo(() => {
    const items = [...(usersQuery.data ?? [])];
    if (!usersRegionFilter) {
      return items;
    }
    return items.filter((user) => String(user.region_id ?? "") === usersRegionFilter);
  }, [usersQuery.data, usersRegionFilter]);

  const sortedUsers = useMemo(() => {
    const items = [...filteredUsers];
    items.sort((left, right) => {
      const leftRole = userRole(left);
      const rightRole = userRole(right);
      const leftRegion = String(left.region_name || left.region_id || "")
        .trim()
        .toLowerCase();
      const rightRegion = String(right.region_name || right.region_id || "")
        .trim()
        .toLowerCase();

      let compare = 0;
      if (sortKey === "username") {
        compare = left.username.localeCompare(right.username, "ru");
      } else if (sortKey === "region") {
        compare = leftRegion.localeCompare(rightRegion, "ru");
      } else if (sortKey === "group") {
        compare = leftRole.localeCompare(rightRole, "ru");
      } else {
        compare =
          Number(left.is_active === true) - Number(right.is_active === true);
      }

      if (compare === 0) {
        compare = left.username.localeCompare(right.username, "ru");
      }
      return sortDirection === "asc" ? compare : -compare;
    });
    return items;
  }, [filteredUsers, sortDirection, sortKey]);

  const availableCreateRoles = useMemo<AccessRole[]>(() => {
    if (access.isAdmin) {
      return ["Заправщик", "Менеджер", "Администратор"];
    }
    if (access.isManager) {
      return ["Заправщик", "Менеджер"];
    }
    return [];
  }, [access.isAdmin, access.isManager]);

  return (
    <div className="page-wrap">
      <section className="card p-4">
        <h1 className="section-title">
          {access.canManageAccess
            ? "Управление доступом"
            : "Управление доступом недоступно"}
        </h1>
        <p className="section-subtitle mt-1">
          {access.canManageAccess
            ? "Создавайте пользователей и управляйте правами."
            : "Этот раздел доступен только менеджерам и администраторам."}
        </p>

        <div className="mt-4">
          {msg ? (
            <div className="muted-box text-sm text-[var(--muted)]">{msg}</div>
          ) : null}
        </div>

        {!access.canManageAccess ? (
          <div className="mt-3 card p-3 md:p-4">
            {!meQuery.data?.telegram_linked ? (
              <a className="btn-app" href="/bot">
                Перейти к привязке бота
              </a>
            ) : (
              <div className="text-sm text-[var(--muted)]">
                Telegram уже привязан к вашей учетной записи.
              </div>
            )}
          </div>
        ) : null}

        {access.canManageAccess ? (
          <div className="mt-3 card p-3 md:p-4">
            <button
              type="button"
              className="w-full rounded-xl border border-transparent p-2 text-left transition hover:border-[var(--border)] hover:bg-[var(--surface-2)]"
              onClick={() => setIsCreateUserModalOpen(true)}
              aria-label="Открыть форму создания пользователя"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span
                    className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--surface-1)] md:h-8 md:w-8"
                    aria-hidden="true"
                  >
                    <UserPlus size={16} />
                  </span>
                  <h2 className="text-sm font-semibold leading-tight">
                    <span className="md:hidden">Сотрудник</span>
                    <span className="hidden md:inline">
                      Создание пользователя
                    </span>
                  </h2>
                </div>
                <span
                  className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--surface-1)] md:h-8 md:w-8"
                  aria-hidden="true"
                >
                  <ChevronRight size={16} />
                </span>
              </div>
            </button>
          </div>
        ) : null}

        {access.canManageAccess ? (
          <div className="mt-4 card p-3 sm:p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-sm font-semibold">Пользователи</h2>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:gap-3">
              <button
                type="button"
                className="btn-app w-full sm:w-auto"
                onClick={() => {
                  setMsg("");
                  usersQuery.refetch();
                }}
              >
                Обновить список
              </button>
              <label className="label-app m-0 w-full sm:w-auto">
                Показ
                <ResponsiveSelect
                  ariaLabel="Показ"
                  value={showAllUsers ? "all" : "active"}
                  disabled={false}
                  onChange={(v) => {
                    setShowAllUsers(v === "all");
                  }}
                  options={[
                    { value: "active", label: "Только активные" },
                    { value: "all", label: "Все сотрудники" },
                  ]}
                />
              </label>
              <label className="label-app m-0 w-full sm:w-auto">
                Регион
                <ResponsiveSelect
                  ariaLabel="Фильтр региона пользователей"
                  value={usersRegionFilter}
                  disabled={false}
                  onChange={(v) => {
                    setUsersRegionFilter(v);
                  }}
                  options={[
                    { value: "", label: "Все регионы" },
                    ...(regionsQuery.data ?? []).map((region) => ({
                      value: String(region.id),
                      label: region.name,
                    })),
                  ]}
                />
              </label>
            </div>
          </div>

          {usersQuery.isPending ? (
            <div className="mt-3 space-y-2">
              {Array.from({ length: 8 }).map((_, idx) => (
                <SkeletonLine key={idx} height={14} width="100%" />
              ))}
            </div>
          ) : usersQuery.data?.length ? (
            isDesktop ? (
              <div className="mt-3 overflow-x-auto">
                <table className="table-app">
                  <thead>
                    <tr>
                      <th>
                        <button
                          type="button"
                          className="btn-app"
                          onClick={() => handleSortClick("username")}
                          title="Сортировать по username"
                        >
                          Username{sortMark("username")}
                        </button>
                      </th>
                      <th>Имя</th>
                      <th>Email</th>
                      <th>Телефон</th>
                      <th>
                        <button
                          type="button"
                          className="btn-app"
                          onClick={() => handleSortClick("status")}
                          title="Сортировать по статусу"
                        >
                          Статус{sortMark("status")}
                        </button>
                      </th>
                      <th>
                        <button
                          type="button"
                          className="btn-app"
                          onClick={() => handleSortClick("group")}
                          title="Сортировать по группе"
                        >
                          Группы{sortMark("group")}
                        </button>
                      </th>
                      <th>
                        <button
                          type="button"
                          className="btn-app"
                          onClick={() => handleSortClick("region")}
                          title="Сортировать по региону"
                        >
                          Регион{sortMark("region")}
                        </button>
                      </th>
                      <th>Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedUsers.map((user) => (
                      <tr key={user.id}>
                        <td className="mono">{user.username}</td>
                        <td>
                          {user.first_name} {user.last_name}
                        </td>
                        <td>{user.email}</td>
                        <td>{user.phone || "—"}</td>
                        <td
                          style={{
                            color: user.is_active
                              ? undefined
                              : "var(--muted)",
                            opacity: user.is_active ? 1 : 0.6,
                            fontWeight: 600,
                          }}
                        >
                          {user.is_active ? "Активен" : "Отключен"}
                        </td>
                        <td
                          style={{
                            color: roleTextColor(userRole(user)),
                            opacity: user.is_active ? 1 : 0.6,
                            fontWeight: 700,
                          }}
                        >
                          {userRole(user)}
                        </td>
                        <td className="mono">
                          {user.region_name || user.region_id || "-"}
                        </td>
                        <td>
                          <button
                            type="button"
                            className="btn-app inline-flex items-center justify-center !p-2"
                            aria-label="Редактировать"
                            title="Редактировать"
                            onClick={() => {
                              setEditingUser(user);
                              setEditForm({
                                email: user.email || "",
                                first_name: user.first_name || "",
                                last_name: user.last_name || "",
                                phone: user.phone || "",
                                region_id: user.region_id
                                  ? String(user.region_id)
                                  : "",
                                role: userRole(user),
                                is_active: user.is_active,
                              });
                              setEditErrors({});
                              setEditUserFeedback("");
                              setEditCredentialsText("");
                              setEditCredentialsCopyStatus("");
                            }}
                          >
                            <Pencil size={14} aria-hidden="true" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="mt-3 space-y-3">
                {sortedUsers.map((user) => (
                  <article
                    key={user.id}
                    className="rounded-xl border border-[var(--border)] bg-[var(--surface-0)] p-3"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="mono text-xs text-[var(--muted)]">
                          {user.username}
                        </div>
                        <div className="mt-1 truncate text-sm font-semibold">
                          {user.first_name} {user.last_name}
                        </div>
                        <div className="mt-1 break-words text-xs text-[var(--muted)]">
                          {user.email}
                        </div>
                      </div>

                      <button
                        type="button"
                        className="btn-app inline-flex shrink-0 items-center justify-center !p-2"
                        aria-label="Редактировать"
                        title="Редактировать"
                        onClick={() => {
                          setEditingUser(user);
                          setEditForm({
                            email: user.email || "",
                            first_name: user.first_name || "",
                            last_name: user.last_name || "",
                            phone: user.phone || "",
                            region_id: user.region_id
                              ? String(user.region_id)
                              : "",
                            role: userRole(user),
                            is_active: user.is_active,
                          });
                          setEditErrors({});
                          setEditUserFeedback("");
                          setEditCredentialsText("");
                          setEditCredentialsCopyStatus("");
                        }}
                      >
                        <Pencil size={14} aria-hidden="true" />
                      </button>
                    </div>

                    <div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                      <div className="text-[var(--muted)]">Телефон</div>
                      <div className="text-right">{user.phone || "—"}</div>
                      <div className="text-[var(--muted)]">Регион</div>
                      <div className="text-right mono">
                        {user.region_name || user.region_id || "-"}
                      </div>
                      <div className="text-[var(--muted)]">Статус</div>
                      <div
                        style={{
                          color: user.is_active
                            ? undefined
                            : "var(--muted)",
                          opacity: user.is_active ? 1 : 0.6,
                          fontWeight: 600,
                        }}
                        className="text-right"
                      >
                        {user.is_active ? "Активен" : "Отключен"}
                      </div>
                      <div className="text-[var(--muted)]">Роль</div>
                      <div
                        style={{
                          color: roleTextColor(userRole(user)),
                          opacity: user.is_active ? 1 : 0.6,
                          fontWeight: 700,
                        }}
                        className="text-right"
                      >
                        {userRole(user)}
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            )
          ) : (
            <div className="mt-3 text-sm text-[var(--muted)]">
              Пользователи не найдены по выбранным фильтрам.
            </div>
          )}
          </div>
        ) : null}

        {access.canManageAccess && isDesktop ? (
          <div className="mt-4 card p-4">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold">События доступа</h2>
            <button
              type="button"
              className="btn-app"
              onClick={() => {
                setIsAccessEventsExpanded((prev) => !prev);
              }}
              aria-label={
                isAccessEventsExpanded
                  ? "Свернуть события доступа"
                  : "Развернуть события доступа"
              }
            >
              {isAccessEventsExpanded ? "-" : "+"}
            </button>
          </div>

          {!isAccessEventsExpanded ? (
            <div className="mt-2 text-sm text-[var(--muted)]">
              Логи скрыты. Нажмите «+», чтобы посмотреть события.
            </div>
          ) : eventsQuery.isPending ? (
            <div className="mt-3 space-y-2">
              {Array.from({ length: 6 }).map((_, idx) => (
                <SkeletonLine key={idx} height={14} width="100%" />
              ))}
            </div>
          ) : eventsQuery.data?.length ? (
            <div className="mt-3 overflow-x-auto">
              <table className="table-app">
                <thead>
                  <tr>
                    {["Когда", "Кто", "Действие", "Детали"].map((h) => (
                      <th key={h}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {eventsQuery.data.map((ev) => (
                    <tr key={ev.id}>
                      <td className="mono">{ev.created_at}</td>
                      <td className="mono">{ev.actor_username}</td>
                      <td>{ev.action}</td>
                      <td>{ev.details}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="mt-2 text-sm text-[var(--muted)]">
              Нет событий.
            </div>
          )}
          </div>
        ) : null}
      </section>
      {access.canManageAccess && isCreateUserModalOpen ? (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.35)",
            display: "grid",
            placeItems: "center",
            zIndex: 50,
            padding: "1rem",
          }}
        >
          <div className="card p-4" style={{ width: "min(900px, 100%)" }}>
            <h3 className="text-base font-semibold">Создание пользователя</h3>
            <form
              className="mt-3 space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                setCreateUserFeedback("");
                setCreateCredentialsText("");
                setCreateCredentialsCopyStatus("");

                const email = String(form.email || "").trim();
                if (!email) {
                  setCreateUserFeedback("Введите `email`.");
                  return;
                }
                const selectedRegionId = form.region_id.trim();
                const regionId =
                  access.isAdmin && selectedRegionId
                    ? Number(selectedRegionId)
                    : null;

                const payload: AccessUserCreateIn = {
                  email,
                  first_name: form.first_name.trim(),
                  last_name: form.last_name.trim(),
                  phone: form.phone.trim(),
                  region_id: regionId,
                  activate: true,
                };
                createUserMutation.mutate({
                  payload,
                  role: form.role,
                });
              }}
            >
              <div
                className="grid gap-3"
                style={{
                  gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
                }}
              >
                <label className="label-app">
                  Имя
                  <input
                    className="input-app"
                    value={form.first_name}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, first_name: e.target.value }))
                    }
                    placeholder="Иван"
                  />
                </label>
                <label className="label-app">
                  Фамилия
                  <input
                    className="input-app"
                    value={form.last_name}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, last_name: e.target.value }))
                    }
                    placeholder="Петров"
                  />
                </label>
                <label className="label-app">
                  Телефон
                  <input
                    className="input-app"
                    value={form.phone}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, phone: e.target.value }))
                    }
                    placeholder="+7 900 000 00 00"
                    autoComplete="tel"
                  />
                </label>
                <label className="label-app">
                  Почта
                  <input
                    className="input-app"
                    value={form.email}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, email: e.target.value }))
                    }
                    placeholder="name@example.com"
                    autoComplete="email"
                  />
                </label>
                <label className="label-app">
                  Роль
                  <ResponsiveSelect
                    ariaLabel="Роль"
                    value={form.role}
                    disabled={false}
                    onChange={(v) => {
                      setForm((prev) => ({
                        ...prev,
                        role: v as AccessRole,
                      }));
                    }}
                    options={availableCreateRoles.map((role) => ({
                      value: role,
                      label: roleLabel(role),
                    }))}
                  />
                </label>
                <label className="label-app">
                  Регион
                  <ResponsiveSelect
                    ariaLabel="Регион"
                    value={form.region_id}
                    disabled={!access.isAdmin}
                    onChange={(v) => {
                      setForm((prev) => ({
                        ...prev,
                        region_id: v,
                      }));
                    }}
                    options={[
                      {
                        value: "",
                        label: access.isAdmin
                          ? "Выберите регион"
                          : "Регион назначается автоматически",
                      },
                      ...(regionsQuery.data ?? []).map((region) => ({
                        value: String(region.id),
                        label: region.name,
                      })),
                    ]}
                  />
                </label>
              </div>
              {!access.isAdmin ? (
                <div className="text-xs text-[var(--muted)]">
                  Менеджер может создать только менеджера или заправщика.
                </div>
              ) : null}

              <div className="toolbar">
                <button
                  type="submit"
                  className="btn-app btn-primary"
                  aria-disabled={createUserMutation.isPending}
                >
                  <span className="inline-flex items-center gap-2">
                    <UserPlus size={14} aria-hidden="true" />
                    <span>
                      {createUserMutation.isPending ? "Создание..." : "Создать"}
                    </span>
                  </span>
                </button>
                <button
                  type="button"
                  className="btn-app"
                  onClick={() => {
                    setIsCreateUserModalOpen(false);
                    setCreateUserFeedback("");
                    setCreateCredentialsText("");
                    setCreateCredentialsCopyStatus("");
                  }}
                >
                  <span className="inline-flex items-center gap-2">
                    <X size={14} aria-hidden="true" />
                    <span>Закрыть</span>
                  </span>
                </button>
              </div>
              {createUserFeedback ? (
                <div className="muted-box text-sm">
                  <div style={{ whiteSpace: "pre-line" }}>{createUserFeedback}</div>
                  {createCredentialsText ? (
                    <div className="toolbar mt-2">
                      <button
                        type="button"
                        className="btn-app"
                        onClick={async () => {
                          try {
                            await navigator.clipboard.writeText(
                              createCredentialsText
                            );
                            setCreateCredentialsCopyStatusWithAutoClear(
                              "Скопировано."
                            );
                          } catch {
                            setCreateCredentialsCopyStatusWithAutoClear(
                              "Не удалось скопировать."
                            );
                          }
                        }}
                      >
                        <span className="inline-flex items-center gap-2">
                          <Check size={14} aria-hidden="true" />
                          <span>Копировать</span>
                        </span>
                      </button>
                      {createCredentialsCopyStatus ? (
                        <span className="text-xs text-[var(--muted)]">
                          {createCredentialsCopyStatus}
                        </span>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </form>
          </div>
        </div>
      ) : null}
      {access.canManageAccess && editingUser ? (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.35)",
            display: "grid",
            placeItems: "center",
            zIndex: 50,
            padding: "1rem",
          }}
        >
          <div className="card p-4" style={{ width: "min(900px, 100%)" }}>
            <h3 className="text-base font-semibold">
              Редактирование сотрудника: {editingUser.username}
            </h3>
            <form
              className="mt-3 space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                const nextErrors = validateEditForm(editForm);
                setEditErrors(nextErrors);
                if (Object.keys(nextErrors).length > 0) {
                  return;
                }
                updateProfileMutation.mutate({
                  userId: editingUser.id,
                  payload: editForm,
                  currentUser: editingUser,
                });
              }}
            >
              <div
                className="grid gap-3"
                style={{
                  gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
                }}
              >
                <label className="label-app">
                  Имя *
                  <input
                    className="input-app"
                    value={editForm.first_name}
                    onChange={(e) =>
                      setEditForm((prev) => ({
                        ...prev,
                        first_name: e.target.value,
                      }))
                    }
                    placeholder="Имя"
                    style={
                      editErrors.first_name
                        ? { borderColor: "#dc2626", boxShadow: "0 0 0 1px #dc2626" }
                        : undefined
                    }
                  />
                  {editErrors.first_name ? (
                    <span className="text-xs" style={{ color: "#dc2626" }}>
                      {editErrors.first_name}
                    </span>
                  ) : null}
                </label>
                <label className="label-app">
                  Фамилия *
                  <input
                    className="input-app"
                    value={editForm.last_name}
                    onChange={(e) =>
                      setEditForm((prev) => ({
                        ...prev,
                        last_name: e.target.value,
                      }))
                    }
                    placeholder="Фамилия"
                    style={
                      editErrors.last_name
                        ? { borderColor: "#dc2626", boxShadow: "0 0 0 1px #dc2626" }
                        : undefined
                    }
                  />
                  {editErrors.last_name ? (
                    <span className="text-xs" style={{ color: "#dc2626" }}>
                      {editErrors.last_name}
                    </span>
                  ) : null}
                </label>
                <label className="label-app">
                  Телефон *
                  <input
                    className="input-app"
                    value={editForm.phone}
                    onChange={(e) =>
                      setEditForm((prev) => ({
                        ...prev,
                        phone: e.target.value,
                      }))
                    }
                    placeholder="+7 900 000 00 00"
                    style={
                      editErrors.phone
                        ? { borderColor: "#dc2626", boxShadow: "0 0 0 1px #dc2626" }
                        : undefined
                    }
                  />
                  {editErrors.phone ? (
                    <span className="text-xs" style={{ color: "#dc2626" }}>
                      {editErrors.phone}
                    </span>
                  ) : null}
                </label>
                <label className="label-app">
                  Почта *
                  <input
                    className="input-app"
                    value={editForm.email}
                    onChange={(e) =>
                      setEditForm((prev) => ({
                        ...prev,
                        email: e.target.value,
                      }))
                    }
                    placeholder="name@example.com"
                    style={
                      editErrors.email
                        ? { borderColor: "#dc2626", boxShadow: "0 0 0 1px #dc2626" }
                        : undefined
                    }
                  />
                  {editErrors.email ? (
                    <span className="text-xs" style={{ color: "#dc2626" }}>
                      {editErrors.email}
                    </span>
                  ) : null}
                </label>
                <label className="label-app">
                  Роль
                  <ResponsiveSelect
                    ariaLabel="Роль"
                    value={editForm.role}
                    disabled={!access.isAdmin}
                    onChange={(v) => {
                      setEditForm((prev) => ({
                        ...prev,
                        role: v as AccessRole,
                      }));
                    }}
                    options={[
                      ...(access.isAdmin
                        ? ([
                            "Заправщик",
                            "Менеджер",
                            "Администратор",
                          ] as AccessRole[])
                        : (["Заправщик"] as AccessRole[])
                      ).map((role) => ({
                        value: role,
                        label: roleLabel(role),
                      })),
                    ]}
                  />
                </label>
                <label className="label-app">
                  Регион
                  <ResponsiveSelect
                    ariaLabel="Регион"
                    value={editForm.region_id}
                    disabled={!access.isAdmin}
                    onChange={(v) => {
                      setEditForm((prev) => ({
                        ...prev,
                        region_id: v,
                      }));
                    }}
                    options={[
                      {
                        value: "",
                        label: access.isAdmin
                          ? "Выберите регион"
                          : "Регион не редактируется",
                      },
                      ...(regionsQuery.data ?? []).map((region) => ({
                        value: String(region.id),
                        label: region.name,
                      })),
                    ]}
                  />
                </label>
              </div>
              <div
                className="muted-box"
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: "1rem",
                }}
              >
                <div>
                  <div className="text-sm font-semibold">Статус учетной записи</div>
                  <div className="text-xs text-[var(--muted)]">
                    Включите, чтобы сотрудник мог входить в систему.
                  </div>
                </div>
                <label
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "0.5rem",
                    cursor: "pointer",
                    userSelect: "none",
                    fontWeight: 600,
                  }}
                >
                  <input
                    type="checkbox"
                    checked={editForm.is_active}
                    onChange={(e) =>
                      setEditForm((prev) => ({
                        ...prev,
                        is_active: e.target.checked,
                      }))
                    }
                    disabled={
                      editingUser.id === currentUserId &&
                      isAdminUser(editingUser) &&
                      editingUser.is_active &&
                      otherActiveAdminsCount === 0
                    }
                  />
                  <span>Активен</span>
                </label>
              </div>
              <div className="muted-box">
                <div className="text-sm font-semibold">
                  Обновление пароля сотрудника
                </div>
                <div className="mt-1 text-xs text-[var(--muted)]">
                  Доступна только генерация временного пароля. После входа
                  пользователь должен установить свой постоянный пароль.
                </div>
                <div className="toolbar mt-3">
                  <button
                    type="button"
                    className="btn-app"
                    aria-disabled={updatePasswordMutation.isPending}
                    onClick={() => {
                      updatePasswordMutation.mutate({
                        userId: editingUser.id,
                        generateTemporary: true,
                      });
                    }}
                  >
                    <span className="inline-flex items-center gap-2">
                      <UserPlus size={14} aria-hidden="true" />
                      <span>Временный пароль</span>
                    </span>
                  </button>
                </div>
              </div>
              {editUserFeedback ? (
                <div className="muted-box text-sm">
                  <div style={{ whiteSpace: "pre-line" }}>{editUserFeedback}</div>
                  {editCredentialsText ? (
                    <div className="toolbar mt-2">
                      <button
                        type="button"
                        className="btn-app"
                        onClick={async () => {
                          try {
                            await navigator.clipboard.writeText(editCredentialsText);
                            setEditCredentialsCopyStatusWithAutoClear("Скопировано.");
                          } catch {
                            setEditCredentialsCopyStatusWithAutoClear(
                              "Не удалось скопировать."
                            );
                          }
                        }}
                      >
                        <span className="inline-flex items-center gap-2">
                          <Check size={14} aria-hidden="true" />
                          <span>Копировать</span>
                        </span>
                      </button>
                      {editCredentialsCopyStatus ? (
                        <span className="text-xs text-[var(--muted)]">
                          {editCredentialsCopyStatus}
                        </span>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ) : null}
              <div className="toolbar">
                <button
                  type="submit"
                  className="btn-app btn-primary"
                  aria-disabled={updateProfileMutation.isPending}
                >
                  <span className="inline-flex items-center gap-2">
                    <Check size={14} aria-hidden="true" />
                    <span>
                      {updateProfileMutation.isPending ? "Сохранение..." : "Сохранить"}
                    </span>
                  </span>
                </button>
                <button
                  type="button"
                  className="btn-app"
                  onClick={() => {
                    setEditingUser(null);
                    setEditUserFeedback("");
                    setEditCredentialsText("");
                    setEditCredentialsCopyStatus("");
                  }}
                >
                  <span className="inline-flex items-center gap-2">
                    <X size={14} aria-hidden="true" />
                    <span>Закрыть</span>
                  </span>
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}

