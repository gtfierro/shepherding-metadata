async function postData(url, data) {
    const response = await fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    }).catch(e => console.error(e));
    return response.json();
}

async function getData(url) {
    const response = await fetch(url, {
        method: 'GET',
    }).catch(e => console.error(e));
    return response.json();
}

window.addEventListener("load", function() {
    console.log("Starting");

    const app = new Vue({
        el: '#app',
        data: {
            graph: null,
        },
        methods: {
            reloadRecords: function() {
                this.updateGraph();
            },
            initGraph: function() {
                // borrowing code from https://gojs.net/latest/samples/conceptMap.html
                var $ = go.GraphObject.make;  // for conciseness in defining templates
                var self = this;
                self.graph = $(go.Diagram, "unifiedBrickGraph",  // must name or refer to the DIV HTML element
                              {
                                initialAutoScale: go.Diagram.Uniform,  // an initial automatic zoom-to-fit
                                contentAlignment: go.Spot.Center,  // align document to the center of the viewport
                                layout: $(go.ForceDirectedLayout, { maxIterations: 200, defaultSpringLength: 10, defaultElectricalCharge: 50 })
                              });

                  // define each Node's appearance
                  self.graph.nodeTemplate = $(go.Node, "Auto",  // the whole node panel
                      { locationSpot: go.Spot.Center },
                      // define the node's outer shape, which will surround the TextBlock
                      $(go.Shape, "Rectangle",
                        { fill: $(go.Brush, "Linear", { 0: "rgb(254, 201, 0)", 1: "rgb(254, 162, 0)" }), stroke: "black" }),
                      $(go.TextBlock,
                        { font: "bold 10pt helvetica, bold arial, sans-serif", margin: 4 },
                        new go.Binding("text", "text"))
                  );

                  // replace the default Link template in the linkTemplateMap
                  self.graph.linkTemplate = $(go.Link,  // the whole link panel
                      $(go.Shape,  // the link shape
                        { stroke: "black" }),
                      $(go.Shape,  // the arrowhead
                        { toArrow: "standard", stroke: null }),
                      $(go.Panel, "Auto",
                        $(go.Shape,  // the label background, which becomes transparent around the edges
                          {
                            fill: $(go.Brush, "Radial", { 0: "rgb(240, 240, 240)", 0.3: "rgb(240, 240, 240)", 1: "rgba(240, 240, 240, 0)" }),
                            stroke: null
                          }),
                        $(go.TextBlock,  // the label text
                          {
                            textAlign: "center",
                            font: "10pt helvetica, arial, sans-serif",
                            stroke: "#555555",
                            margin: 4
                          },
                          new go.Binding("text", "text"))
                      )
                    );
                self.graph.model = new go.GraphLinksModel([], []);
                console.log(self.graph.model);
            },
            updateGraph: function() {
                console.log("Updating graph");
                this.graph.model = new go.GraphLinksModel([], []);
                var graph = this.graph;
                getData('http://localhost:6483/graph').then(data => {
                    data = data['@graph'];
                    graph.startTransaction("t");
                    data.forEach(ent => {
                        let entity = ent['@id'];
                        graph.model.addNodeData({
                            key: entity,
                            text: entity,
                        });
                        
                        let entity_type = ent['@type']['@id'];
                        graph.model.addNodeData({
                            key: entity_type,
                            text: entity_type,
                        });
                        graph.model.addLinkData({
                            from: entity,
                            to: entity_type,
                            link: "type",
                        });
                        for (const prop in ent) {
                            if (prop == '@id' || prop == '@type') continue;

                            // try to read it as a single property first
                            var o = ent[prop]['@id'] || ent[prop]['@value'];
                            if (o != null) {
                                graph.model.addLinkData({
                                    from: entity,
                                    to: o,
                                    text: prop,
                                })
                                continue;
                            }
                            // if this fails, read as a list
                            ent[prop].forEach(obj => {
                                var o = obj['@id'] || obj['@value'];
                                graph.model.addLinkData({
                                    from: entity,
                                    to: o,
                                    text: prop,
                                })
                            });
                        }
                    });
                    graph.commitTransaction("t");
                });
            },
        },
        mounted() {
            this.initGraph();
            this.updateGraph();
        },
    });

});
