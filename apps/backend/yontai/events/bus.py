from collections.abc import Callable

from yontai.events.schemas import DomainEvent

EventHandler = Callable[[DomainEvent], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[EventHandler] = []

    def subscribe(self, handler: EventHandler) -> None:
        self._subscribers.append(handler)

    def publish(self, event: DomainEvent) -> None:
        for handler in self._subscribers:
            handler(event)


event_bus = EventBus()
