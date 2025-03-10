package graphql

import (
	"github.com/graphql-go/graphql"
	"github.com/img-battle-engine/core/search"
)

// 定義GraphQL類型
var searchResultType = graphql.NewObject(
	graphql.ObjectConfig{
		Name: "SearchResult",
		Fields: graphql.Fields{
			"id": &graphql.Field{
				Type: graphql.String,
			},
			"score": &graphql.Field{
				Type: graphql.Float,
			},
			"text": &graphql.Field{
				Type: graphql.String,
			},
			"episode": &graphql.Field{
				Type: graphql.Int,
			},
			"startTime": &graphql.Field{
				Type: graphql.String,
			},
			"endTime": &graphql.Field{
				Type: graphql.String,
			},
			"collection": &graphql.Field{
				Type: graphql.String,
			},
		},
	},
)

// Schema 定義GraphQL schema
func NewSchema(searchEngine search.SearchEngine) (graphql.Schema, error) {
	return graphql.NewSchema(
		graphql.SchemaConfig{
			Query: graphql.NewObject(
				graphql.ObjectConfig{
					Name: "Query",
					Fields: graphql.Fields{
						"search": &graphql.Field{
							Type: graphql.NewList(searchResultType),
							Args: graphql.FieldConfigArgument{
								"query": &graphql.ArgumentConfig{
									Type: graphql.NewNonNull(graphql.String),
								},
								"collection": &graphql.ArgumentConfig{
									Type: graphql.String,
								},
								"limit": &graphql.ArgumentConfig{
									Type:         graphql.Int,
									DefaultValue: 10,
								},
							},
							Resolve: func(p graphql.ResolveParams) (interface{}, error) {
								query := p.Args["query"].(string)
								limit := p.Args["limit"].(int)

								// 檢查是否指定了集合
								if col, ok := p.Args["collection"].(string); ok && col != "" && col != "all" {
									return searchEngine.Search(query, col, limit)
								}

								// 如果沒有指定集合或指定為"all"，則搜索所有集合
								return searchEngine.SearchAll(query, limit)
							},
						},
					},
				},
			),
		},
	)
}
