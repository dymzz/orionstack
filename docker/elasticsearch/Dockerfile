# OrionStack Elasticsearch image with IK Chinese analyzer.
#
# The IK plugin version MUST match the Elasticsearch base image version
# exactly, otherwise the node will refuse to start.
FROM elasticsearch:8.17.0

RUN bin/elasticsearch-plugin install --batch \
    https://release.infinilabs.com/analysis-ik/stable/elasticsearch-analysis-ik-8.17.0.zip
