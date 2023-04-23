import os
import typing
import asyncio
import logging

import rich
import aiohttp
import rich.progress

import rez_pip.pip

_LOG = logging.getLogger(__name__)
_lock = asyncio.Lock()


def downloadPackages(
    packages: typing.List[rez_pip.pip.PackageInfo], dest: str
) -> typing.List[str]:
    return asyncio.run(_downloadPackages(packages, dest))


async def _downloadPackages(
    packages: typing.List[rez_pip.pip.PackageInfo], dest: str
) -> typing.List[str]:
    items: typing.List[
        typing.Coroutine[typing.Any, typing.Any, typing.Optional[str]]
    ] = []
    wheels = []

    async with aiohttp.ClientSession() as session:
        with rich.progress.Progress(
            "[progress.description]{task.description}",
            "[progress.percentage]{task.percentage:>3.0f}%",
            rich.progress.BarColumn(),
            rich.progress.DownloadColumn(),
            rich.progress.TransferSpeedColumn(),
            transient=True,
            console=rich.get_console(),
        ) as progress:
            tasks: typing.Dict[str, rich.progress.TaskID] = {}

            # Create all the downlod tasks first
            for package in packages:
                tasks[package.name] = progress.add_task(package.name)

            # Then create the "total" progress bar. This ensures that total is at the bottom.
            mainTask = progress.add_task(f"[bold]Total (0/{len(packages)})", total=0)

            for package in packages:
                items.append(
                    download(
                        package, dest, session, progress, tasks[package.name], mainTask
                    )
                )

            wheels = await asyncio.gather(*items)

    if not all(wheels):
        raise RuntimeError("Some wheels failed to be downloaded")

    return wheels


async def download(
    package: rez_pip.pip.PackageInfo,
    target: str,
    session: aiohttp.ClientSession,
    progress: rich.progress.Progress,
    taskID: rich.progress.TaskID,
    mainTaskID: rich.progress.TaskID,
) -> typing.Optional[str]:
    _LOG.debug(
        f"Downloading {package.name}-{package.version} from {package.download_info.url}"
    )

    async with session.get(
        package.download_info.url,
        headers={
            "Content-Type": "application/octet-stream",
            "User-Agent": "rez-pip/0.1.0",
        },
    ) as response:
        size = int(response.headers.get("content-length", 0))
        progress.update(taskID, total=size)

        async with _lock:
            mainTask = [task for task in progress.tasks if task.id == mainTaskID][0]

            progress.update(
                mainTaskID,
                total=typing.cast(int, mainTask.total) + size,
            )

        if response.status != 200:
            _LOG.error(
                f"failed to download {package.download_info.url}: {response.status} - {response.reason}, {response.request_info}"
            )
            return None

        wheelName: str = os.path.basename(package.download_info.url)
        wheelPath = os.path.join(target, wheelName)
        with open(wheelPath, "wb") as fd:
            async for chunk, asd in response.content.iter_chunks():
                if not chunk:
                    break
                progress.update(taskID, advance=len(chunk))
                progress.update(mainTaskID, advance=len(chunk))
                fd.write(chunk)

    progress.update(taskID, visible=False)

    total = len(progress.tasks) - 1
    async with _lock:
        completedItems = [task for task in progress.tasks if not task.visible]
        progress.update(
            mainTaskID, description=f"[bold]Total ({len(completedItems)}/{total})"
        )
    _LOG.info(
        f"Downloaded {package.name}-{package.version} to {wheelPath!r} ({os.stat(wheelPath).st_size} bytes)"
    )

    return wheelPath
