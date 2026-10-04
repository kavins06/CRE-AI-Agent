"""Database guards, including SQLite REPLACE and PostgreSQL TRUNCATE."""

from collections.abc import Callable
from typing import cast

from sqlalchemy import DDL, MetaData, UniqueConstraint, event

# SQLAlchemy documents this signature but leaves its DDL constructor untyped.
ddl = cast(Callable[[str], DDL], DDL)


def register_append_only(metadata: MetaData, names: tuple[str, ...]) -> None:
    event.listen(
        metadata,
        "before_create",
        ddl(
            "CREATE OR REPLACE FUNCTION cre_state_reject_mutation() RETURNS trigger "
            "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'append-only state'; END; $$"
        ).execute_if(dialect="postgresql"),
    )
    for name in names:
        table = metadata.tables[name]
        for action in ("UPDATE", "DELETE"):
            event.listen(
                table,
                "after_create",
                ddl(
                    f"CREATE TRIGGER {name}_no_{action.lower()} BEFORE {action} "
                    "ON %(fullname)s BEGIN SELECT RAISE(ABORT, 'append-only state'); END"
                ).execute_if(dialect="sqlite"),
            )
        # REPLACE silently deletes conflicts unless recursive triggers are enabled.
        constraints = [table.primary_key] + [
            constraint
            for constraint in table.constraints
            if isinstance(constraint, UniqueConstraint)
        ]
        conflicts = " OR ".join(
            "(" + " AND ".join(f"{column.name} = NEW.{column.name}" for column in c.columns) + ")"
            for c in constraints
        )
        event.listen(
            table,
            "after_create",
            ddl(
                f"CREATE TRIGGER {name}_no_replace BEFORE INSERT ON %(fullname)s "
                f"WHEN EXISTS (SELECT 1 FROM %(fullname)s WHERE {conflicts}) "
                "BEGIN SELECT RAISE(ABORT, 'append-only state'); END"
            ).execute_if(dialect="sqlite"),
        )
        for actions, suffix, level in (
            ("UPDATE OR DELETE", "mutation", "ROW"),
            ("TRUNCATE", "truncate", "STATEMENT"),
        ):
            event.listen(
                table,
                "after_create",
                ddl(
                    f"CREATE TRIGGER {name}_no_{suffix} BEFORE {actions} ON %(fullname)s "
                    f"FOR EACH {level} EXECUTE FUNCTION cre_state_reject_mutation()"
                ).execute_if(dialect="postgresql"),
            )
