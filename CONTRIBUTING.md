# Contributing

**Working on your first Pull Request?** You can learn how from this *free* series [How to Contribute to an Open Source Project on GitHub](https://kcd.im/pull-request)


Always wanted to work on cool APP for people to use? Here is your chance!

New innovative HI-tech project is waiting for your skills, inspiration and commitment.
Join BitDust team and be a part of a great open source development!
Read more about [how to join][join] the project and have fun coding together.


To start you need to fork, then clone the repo:

    git clone git@github.com:<your-username>/devel.git bitdust.devel


Deploy and Run BitDust software locally on your machine:

    cd bitdust.devel
    python3 bitdust.py install
    sudo ln -s -f /Users/veselin/.bitdust/bitdust /usr/local/bin/bitdust
    bitdust


Make sure the unit tests pass:

    make test_unit


Run regression tests via Docker:

    make regress_full


Make your change. Add tests for your change. Make the tests pass:

    make

Push to your fork and [submit a pull request][pr].

Sometimes build is failed, we still have non-stable regression tests, just re-run the failed build in that case.

At this point you're waiting on us, but we will reach you soon to cooperate.

Please attach your PR to one of the [opened issues][issues] so we can keep discussions in correct places.

Any idea for improvement in the process?
Contuct us directly on info`@`bitdust.io or join our [Telegram group](https://t.me/bitdust) to keep in touch.


[pr]: https://github.com/bitdust-io/devel/compare/
[issues]: https://github.com/bitdust-io/devel/issues/
[join]: https://bitdust.io/wiki/contribution.html
