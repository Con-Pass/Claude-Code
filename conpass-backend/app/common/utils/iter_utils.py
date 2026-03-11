from typing import Sized, List


def iterable_split(sized_iterable: Sized, n: int) -> List[Sized]:
    return [sized_iterable[i:i + n] for i in range(0, len(sized_iterable), n)]
