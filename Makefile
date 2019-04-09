SSH_KEY := $(HOME)/.ssh/gcloud
RUN_OPTS := --private-key=$(SSH_KEY)
RUN := ansible-playbook $(RUN_OPTS)

.PHONY: all setup-cluster create-nodes ubuntu-install master workers clean clean-all


all: create-nodes setup-cluster

setup-cluster: ubuntu-install master workers

create-nodes:
	./create-nodes.py
	# Give time for nodes to start up.
	sleep 2m

ubuntu-install:
	$(RUN) kube-dependencies-ubuntu.yaml

master:
	$(RUN) master-node.yaml

workers:
	$(RUN) worker-nodes.yaml

clean:
	rm -rf kube-dependencies-ubuntu.retry
	rm -rf master-node.retry
	rm -rf worker-nodes.retry

clean-all: clean
	gcloud compute instances delete node-0 node-1 node-2 node-3
	rm -rf hosts
