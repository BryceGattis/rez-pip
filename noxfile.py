"""Development automation"""
import nox

# nox.options.sessions = ["lint", "test", "doctest"]
nox.options.reuse_existing_virtualenvs = True


@nox.session()
def lint(session: nox.Session):
    pass


@nox.session(python=["3.7", "3.8", "3.9", "3.10", "3.11"])
def test(session: nox.Session):
    session.install("-r", "tests/requirements.txt")
    session.install(".")

    session.run(
        "pytest", "-v", "--cov=rez_pip", "--cov-report=term-missing", *session.posargs
    )


@nox.session()
def update_pip(session: nox.Session):
    pass
