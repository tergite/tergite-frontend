# API Design

This document contains the basic API (Application Programming Interface) design followed for the RESTful API exposed by MSS.

It contains rules we follow so that any developer working with the API can find it predictable to work with.

## Rules

- The format for the URL for each resource is `http(s)://{subdomain}.{domain}/{resource}/({id})` 
  _Note: the parts in `()` are optional._
- Every resource has a schema that represents the JSON object for every instance of that resource. 
  For example, the jobs resource has a `Job` JSON object schema. 
- Endpoints that return many results return a paginated object of format:

```json
{
  "skip": "<number>",
  "limit": "<number | null>",
  "data": "<ResourceJSONSchema[]>"
}
```

- Endpoints that perform an action (e.g. trigger calibration) return a status message object of format:

```json
{
  "status": "<'SUCCESS' | 'FAILURE' | 'PENDING' | 'ERROR'>",
  "message": "<string | null>"
}
```

- When an error is thrown in the endpoint, the status code is set to a value outside the 200-30X range 
  and the response is a JSON object of format:

```json
{
  "detail": "<string>"
}
```

- Every resource has at least five endpoints:

    - GetOne (GET `/{resource}/({id})`)
    - GetMany (GET `/{resource}/?{query_param1}={query_param1_value}&{query_param2}={query_param2_value}`)
    - UpdateOne (PUT `/{resource}/({id})`)
    - CreateOne (POST `/{resource}/`)

- Resources may also have the following optional endpoints:

    - UpdateMany (PUT `/{resource}/?{query_param1}={query_param1_value}&{query_param2}={query_param2_value}`)
    - DeleteOne (DELETE `/{resource}/({id})`)
    - DeleteMany (DELETE `/{resource}/?{query_param1}={query_param1_value}&{query_param2}={query_param2_value}`)

- We can also have `GET`-only endpoints for specific properties of a resource with path format `/{resource}/{property}`
  Such endpoints are only allowed if:

    - The given property is much more frequently requested for, compared to the rest of the object e.g. 'status' of a job
- The response from endpoints that return specific properties of a resource is a JSON object format:

```json
{
  "{property}": "<any>"
}
```

## Objectives

- Ensure a very minimal interface surface, with as few endpoints as possible
- Have only one way of doing one thing, except only for cases where the performance or/and readability heavily outweigh
  the advantage of a shallow learning curve
- The endpoint pattern should be predictable enough that if one knows the resource name, one can easily construct 
  any endpoint without having to check the API documentation.
- All responses need to be JSON-compatible so that client code is simple. 
  It will not need to handle other types of responses.
